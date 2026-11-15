from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, case
from sqlalchemy.orm import Session
from ..db import get_db
from ..inventory_costing import replay_fifo_layers, issue_fifo_layers, fifo_layer_totals
from ..dependencies import current_user, require_org_permission
from ..models import (
    AuditEvent, ERPAccount, ERPDocument, ERPDocumentLine, ERPItem, ERPJournalEntry,
    ERPJournalLine, ERPParty, ERPStockLedger, ERPTaxCode, FinancialYear, Facility,
    GSTRegistration, ERPPayment, ERPPaymentAllocation, ERPBankAccount, ERPBankStatementLine,
    Membership, User,
)

router = APIRouter(prefix="/v1/erp", tags=["shared ERP"])
CENT = Decimal("0.01")

def money(value):
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)

def split_gst_components(tax_amount, seller_state, place_state):
    total = money(tax_amount)
    if total == 0:
        return Decimal("0.00"), Decimal("0.00"), Decimal("0.00")
    if not seller_state or not place_state:
        raise ValueError("Seller GST state and place-of-supply state are required")
    if seller_state == place_state:
        cgst = money(total / Decimal("2"))
        return cgst, money(total - cgst), Decimal("0.00")
    return Decimal("0.00"), Decimal("0.00"), total

class ItemIn(BaseModel):
    item_code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=2, max_length=200)
    item_type: str = Field(default="goods", pattern="^(goods|service)$")
    unit: str = Field(default="Nos", max_length=20)
    hsn_sac: str | None = Field(default=None, max_length=20)
    default_tax_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    purchase_price: Decimal = Field(default=Decimal("0"), ge=0)
    selling_price: Decimal = Field(default=Decimal("0"), ge=0)
    track_stock: bool = True

class PartyIn(BaseModel):
    party_code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=2, max_length=200)
    party_type: str = Field(pattern="^(customer|supplier|both)$")
    gstin: str | None = Field(default=None, min_length=15, max_length=15)
    pan: str | None = Field(default=None, min_length=10, max_length=10)
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    state_code: str | None = Field(default=None, pattern="^[0-9]{2}$")
    credit_days: int = Field(default=0, ge=0, le=365)

class TaxCodeIn(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=2, max_length=100)
    rate: Decimal = Field(ge=0, le=100)
    is_exempt: bool = False

class DocumentLineIn(BaseModel):
    item_id: int
    tax_code_id: int | None = None
    description: str | None = Field(default=None, max_length=250)
    quantity: Decimal = Field(gt=0, le=100000000)
    unit_price: Decimal = Field(ge=0, le=1000000000)
    discount_amount: Decimal = Field(default=Decimal("0"), ge=0)

class PaymentAllocationIn(BaseModel):
    document_id: int
    amount: Decimal = Field(ge=Decimal("0.01"))

class PaymentIn(BaseModel):
    payment_no: str = Field(min_length=1, max_length=60)
    payment_type: str = Field(pattern="^(customer_receipt|supplier_payment)$")
    party_id: int
    payment_date: date
    amount: Decimal = Field(ge=Decimal("0.01"), le=100000000000)
    method: str = Field(default="bank", pattern="^(cash|bank|upi|cheque|card|other)$")
    bank_account_id: int | None = None
    reference: str | None = Field(default=None, max_length=100)
    allocations: list[PaymentAllocationIn] = Field(default_factory=list, max_length=100)

class BankAccountIn(BaseModel):
    account_code: str = Field(min_length=2, max_length=30)
    bank_name: str = Field(min_length=2, max_length=120)
    account_label: str = Field(min_length=2, max_length=120)
    account_last4: str | None = Field(default=None, pattern="^[0-9]{4}$")

class BankStatementLineIn(BaseModel):
    bank_account_id: int
    transaction_date: date
    description: str = Field(min_length=2, max_length=250)
    reference: str | None = Field(default=None, max_length=100)
    direction: str = Field(pattern="^(debit|credit)$")
    amount: Decimal = Field(gt=0, le=100000000000)

class DocumentIn(BaseModel):
    document_type: str = Field(pattern="^(sales_invoice|purchase_bill)$")
    document_no: str = Field(min_length=1, max_length=60)
    party_id: int
    facility_id: int | None = None
    issue_date: date
    due_date: date | None = None
    place_of_supply_state: str | None = Field(default=None, pattern="^[0-9]{2}$")
    lines: list[DocumentLineIn] = Field(min_length=1, max_length=200)

def _audit(db, membership, user, action, resource, rid, detail):
    db.add(AuditEvent(organisation_id=membership.organisation_id, actor_user_id=user.id,
        action=action, resource_type=resource, resource_id=str(rid), detail=detail))

def _account(db, org_id, code):
    row = db.query(ERPAccount).filter_by(organisation_id=org_id, account_code=code, is_active=True).first()
    if not row:
        raise HTTPException(500, detail=f"Required ledger account {code} is not configured")
    return row

@router.get("/items")
def list_items(m: Membership = Depends(require_org_permission("erp.read")), db: Session = Depends(get_db)):
    return db.query(ERPItem).filter_by(organisation_id=m.organisation_id, is_active=True).order_by(ERPItem.item_code).all()

@router.post("/items", status_code=201)
def create_item(p: ItemIn, m: Membership = Depends(require_org_permission("erp.manage")), u: User = Depends(current_user), db: Session = Depends(get_db)):
    row = ERPItem(organisation_id=m.organisation_id, **p.model_dump())
    db.add(row)
    try:
        db.flush()
        _audit(db,m,u,"erp.item.created","erp_item",row.id,f"Created item {row.item_code}")
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(409, detail="Item code already exists or item data is invalid")
    db.refresh(row)
    return row

@router.get("/parties")
def list_parties(m: Membership = Depends(require_org_permission("erp.read")), db: Session = Depends(get_db)):
    return db.query(ERPParty).filter_by(organisation_id=m.organisation_id, is_active=True).order_by(ERPParty.name).all()

@router.post("/parties", status_code=201)
def create_party(p: PartyIn, m: Membership = Depends(require_org_permission("erp.manage")), u: User = Depends(current_user), db: Session = Depends(get_db)):
    data=p.model_dump()
    if data["gstin"]: data["gstin"]=data["gstin"].upper()
    if data["pan"]: data["pan"]=data["pan"].upper()
    row=ERPParty(organisation_id=m.organisation_id,**data)
    db.add(row)
    try:
        db.flush(); _audit(db,m,u,"erp.party.created","erp_party",row.id,f"Created {row.party_type} {row.party_code}"); db.commit()
    except Exception:
        db.rollback(); raise HTTPException(409,detail="Party code already exists or data is invalid")
    db.refresh(row); return row

@router.get("/tax-codes")
def list_tax_codes(m: Membership = Depends(require_org_permission("erp.read")), db: Session = Depends(get_db)):
    return db.query(ERPTaxCode).filter_by(organisation_id=m.organisation_id,is_active=True).order_by(ERPTaxCode.rate).all()

@router.post("/tax-codes",status_code=201)
def create_tax_code(p: TaxCodeIn,m: Membership=Depends(require_org_permission("erp.manage")),u: User=Depends(current_user),db: Session=Depends(get_db)):
    row=ERPTaxCode(organisation_id=m.organisation_id,**p.model_dump());db.add(row)
    try:
        db.flush();_audit(db,m,u,"erp.tax_code.created","erp_tax_code",row.id,f"Created tax code {row.code}");db.commit()
    except Exception:
        db.rollback();raise HTTPException(409,detail="Tax code already exists")
    db.refresh(row);return row

@router.get("/documents")
def list_documents(m: Membership=Depends(require_org_permission("erp.read")),db: Session=Depends(get_db)):
    return db.query(ERPDocument).filter_by(organisation_id=m.organisation_id).order_by(ERPDocument.issue_date.desc(),ERPDocument.id.desc()).limit(500).all()

@router.post("/documents",status_code=201)
def create_document(p: DocumentIn,m: Membership=Depends(require_org_permission("erp.manage")),u: User=Depends(current_user),db: Session=Depends(get_db)):
    org=m.organisation_id
    party=db.query(ERPParty).filter_by(id=p.party_id,organisation_id=org,is_active=True).first()
    expected="customer" if p.document_type=="sales_invoice" else "supplier"
    if not party or party.party_type not in {expected,"both"}:
        raise HTTPException(422,detail=f"Select an active {expected} belonging to this organisation")
    if p.facility_id and not db.query(Facility.id).filter_by(id=p.facility_id,organisation_id=org,is_active=True).first():
        raise HTTPException(422,detail="Facility does not belong to this organisation")
    if p.due_date and p.due_date<p.issue_date: raise HTTPException(422,detail="Due date cannot precede issue date")
    if db.query(ERPDocument.id).filter_by(organisation_id=org,document_no=p.document_no).first():
        raise HTTPException(409,detail="Document number already exists")
    registration_q=db.query(GSTRegistration).filter_by(organisation_id=org,is_active=True,is_primary=True)
    if p.facility_id:
        registration_q=registration_q.filter((GSTRegistration.facility_id==p.facility_id) | (GSTRegistration.facility_id.is_(None)))
    else:
        registration_q=registration_q.filter(GSTRegistration.facility_id.is_(None))
    seller_registration=registration_q.order_by(GSTRegistration.facility_id.desc()).first()
    seller_state=seller_registration.state_code if seller_registration else None
    place_state=p.place_of_supply_state or (party.state_code if p.document_type=="sales_invoice" else seller_state)
    doc=ERPDocument(organisation_id=org,facility_id=p.facility_id,party_id=party.id,document_type=p.document_type,
        document_no=p.document_no,issue_date=p.issue_date,due_date=p.due_date,place_of_supply_state=place_state,
        created_by_user_id=u.id,status="draft")
    db.add(doc);db.flush()
    for line in p.lines:
        item=db.query(ERPItem).filter_by(id=line.item_id,organisation_id=org,is_active=True).first()
        if not item: db.rollback();raise HTTPException(422,detail=f"Item {line.item_id} is unavailable in this organisation")
        tax=None
        if line.tax_code_id:
            tax=db.query(ERPTaxCode).filter_by(id=line.tax_code_id,organisation_id=org,is_active=True).first()
            if not tax: db.rollback();raise HTTPException(422,detail="Tax code does not belong to this organisation")
        discount=money(line.discount_amount);gross=money(line.quantity*line.unit_price)
        if discount>gross: db.rollback();raise HTTPException(422,detail="Line discount cannot exceed its gross amount")
        taxable=money(gross-discount);rate=Decimal("0") if not tax or tax.is_exempt else Decimal(tax.rate)
        tax_amount=money(taxable*rate/Decimal("100"))
        try:
            cgst,sgst,igst=split_gst_components(tax_amount,seller_state,place_state)
        except ValueError as exc:
            db.rollback()
            raise HTTPException(422,detail=str(exc))
        db.add(ERPDocumentLine(document_id=doc.id,item_id=item.id,tax_code_id=tax.id if tax else None,
            description=line.description or item.name,quantity=line.quantity,unit_price=line.unit_price,
            discount_amount=discount,tax_rate=rate,taxable_amount=taxable,tax_amount=tax_amount,
            cgst_amount=cgst,sgst_amount=sgst,igst_amount=igst,line_total=taxable+tax_amount))
    _audit(db,m,u,"erp.document.draft_created","erp_document",doc.id,f"Created draft {p.document_type} {p.document_no}")
    db.commit();db.refresh(doc);return doc

@router.post("/documents/{document_id}/post")
def post_document(document_id:int,m:Membership=Depends(require_org_permission("erp.manage")),u:User=Depends(current_user),db:Session=Depends(get_db)):
    org=m.organisation_id
    doc=db.query(ERPDocument).filter_by(id=document_id,organisation_id=org).with_for_update().first()
    if not doc: raise HTTPException(404,detail="Document not found")
    if doc.status!="draft": raise HTTPException(409,detail="Only draft documents can be posted")
    fy=db.query(FinancialYear).filter(FinancialYear.organisation_id==org,FinancialYear.start_date<=doc.issue_date,FinancialYear.end_date>=doc.issue_date).first()
    if db.query(FinancialYear.id).filter_by(organisation_id=org).first() and (not fy or fy.is_closed):
        raise HTTPException(409,detail="Document date is outside an open financial year")
    party=db.query(ERPParty).filter_by(id=doc.party_id,organisation_id=org).first()
    lines=db.query(ERPDocumentLine).filter_by(document_id=doc.id).all()
    if not lines: raise HTTPException(409,detail="Document has no lines")
    subtotal=sum((Decimal(x.taxable_amount) for x in lines),Decimal("0"))
    tax_total=sum((Decimal(x.tax_amount) for x in lines),Decimal("0"))
    grand=money(subtotal+tax_total)
    if grand<=0: raise HTTPException(422,detail="Document total must be greater than zero")
    inbound=doc.document_type=="purchase_bill"
    party_account=_account(db,org,"2000" if inbound else "1100")
    base_account=_account(db,org,"1200" if inbound else "4000")
    tax_accounts = {
        "cgst": _account(db,org,"1310" if inbound else "2110"),
        "sgst": _account(db,org,"1320" if inbound else "2120"),
        "igst": _account(db,org,"1330" if inbound else "2130"),
    }
    journal=ERPJournalEntry(organisation_id=org,document_id=doc.id,entry_no=f"ERP-{doc.document_no}",entry_date=doc.issue_date,
        narration=f"{doc.document_type.replace('_',' ').title()} {doc.document_no}",posted_by_user_id=u.id)
    db.add(journal);db.flush()
    def jl(account,debit=0,credit=0):
        db.add(ERPJournalLine(journal_entry_id=journal.id,account_id=account.id,debit=money(debit),credit=money(credit),party_id=party.id))
    cgst_total=sum((Decimal(x.cgst_amount) for x in lines),Decimal("0"))
    sgst_total=sum((Decimal(x.sgst_amount) for x in lines),Decimal("0"))
    igst_total=sum((Decimal(x.igst_amount) for x in lines),Decimal("0"))
    if inbound:
        jl(base_account,debit=subtotal)
        if cgst_total: jl(tax_accounts["cgst"],debit=cgst_total)
        if sgst_total: jl(tax_accounts["sgst"],debit=sgst_total)
        if igst_total: jl(tax_accounts["igst"],debit=igst_total)
        jl(party_account,credit=grand)
    else:
        jl(party_account,debit=grand);jl(base_account,credit=subtotal)
        if cgst_total: jl(tax_accounts["cgst"],credit=cgst_total)
        if sgst_total: jl(tax_accounts["sgst"],credit=sgst_total)
        if igst_total: jl(tax_accounts["igst"],credit=igst_total)
    fifo_layers_by_item = {}
    cogs_total = Decimal("0.00")
    inventory_account = _account(db,org,"1200")
    cogs_account = _account(db,org,"5000")
    for line in lines:
        item=db.query(ERPItem).filter_by(id=line.item_id,organisation_id=org).with_for_update().first()
        if item.track_stock and item.item_type=="goods":
            if item.id not in fifo_layers_by_item:
                history=db.query(ERPStockLedger).filter(
                    ERPStockLedger.organisation_id==org,ERPStockLedger.item_id==item.id,
                    ERPStockLedger.facility_id==doc.facility_id).order_by(
                    ERPStockLedger.movement_date,ERPStockLedger.id).with_for_update().all()
                if history and doc.issue_date < history[-1].movement_date:
                    db.rollback()
                    raise HTTPException(409,detail=f"Backdated stock posting is not allowed for {item.item_code}; latest movement is {history[-1].movement_date}")
                try:
                    fifo_layers_by_item[item.id]=replay_fifo_layers(history)
                except ValueError as exc:
                    db.rollback()
                    raise HTTPException(409,detail=f"Existing stock history for {item.item_code} needs reconciliation: {exc}")
            layers=fifo_layers_by_item[item.id]
            if inbound:
                net_unit_cost=Decimal(line.taxable_amount)/Decimal(line.quantity)
                layers.append({"quantity":Decimal(line.quantity),"unit_cost":net_unit_cost})
                movement_cost=money(net_unit_cost)
            else:
                try:
                    movement_cost=issue_fifo_layers(layers,Decimal(line.quantity))
                except ValueError:
                    available=sum((x["quantity"] for x in layers),Decimal("0"))
                    db.rollback()
                    raise HTTPException(409,detail=f"Insufficient FIFO stock for {item.item_code}; available {available}")
                cogs_total += movement_cost
            db.add(ERPStockLedger(organisation_id=org,facility_id=doc.facility_id,item_id=item.id,document_id=doc.id,
                movement_date=doc.issue_date,quantity_in=line.quantity if inbound else 0,
                quantity_out=0 if inbound else line.quantity,unit_cost=movement_cost if inbound else money(movement_cost/Decimal(line.quantity))))
    if not inbound and cogs_total:
        jl(cogs_account,debit=money(cogs_total))
        jl(inventory_account,credit=money(cogs_total))
    # Assert the journal is balanced before the transaction is committed.
    debit=sum((Decimal(x.debit) for x in db.query(ERPJournalLine).filter_by(journal_entry_id=journal.id).all()),Decimal("0"))
    credit=sum((Decimal(x.credit) for x in db.query(ERPJournalLine).filter_by(journal_entry_id=journal.id).all()),Decimal("0"))
    if money(debit)!=money(credit): db.rollback();raise HTTPException(500,detail="Generated journal is not balanced")
    doc.subtotal=money(subtotal);doc.tax_total=money(tax_total);doc.grand_total=grand
    doc.status="posted";doc.posted_at=datetime.now(timezone.utc)
    _audit(db,m,u,"erp.document.posted","erp_document",doc.id,f"Posted {doc.document_type} {doc.document_no}; total {grand}")
    db.commit();db.refresh(doc)
    return {"document":doc,"journal_entry_id":journal.id,"debit_total":money(debit),"credit_total":money(credit)}

@router.get("/stock-balances")
def stock_balances(facility_id:int|None=None,m:Membership=Depends(require_org_permission("erp.read")),db:Session=Depends(get_db)):
    q=db.query(ERPStockLedger.item_id,ERPItem.item_code,ERPItem.name,ERPStockLedger.facility_id,
        func.sum(ERPStockLedger.quantity_in-ERPStockLedger.quantity_out).label("quantity_on_hand")).join(
        ERPItem,ERPItem.id==ERPStockLedger.item_id).filter(ERPStockLedger.organisation_id==m.organisation_id)
    if facility_id is not None:q=q.filter(ERPStockLedger.facility_id==facility_id)
    rows=q.group_by(ERPStockLedger.item_id,ERPItem.item_code,ERPItem.name,ERPStockLedger.facility_id).order_by(ERPItem.item_code).all()
    return [{"item_id":r.item_id,"item_code":r.item_code,"name":r.name,"facility_id":r.facility_id,"quantity_on_hand":str(r.quantity_on_hand)} for r in rows]


@router.get("/inventory-valuation")
def inventory_valuation(facility_id:int|None=None,m:Membership=Depends(require_org_permission("erp.read")),db:Session=Depends(get_db)):
    q=db.query(ERPStockLedger).filter(ERPStockLedger.organisation_id==m.organisation_id)
    if facility_id is not None:
        if not db.query(Facility.id).filter_by(id=facility_id,organisation_id=m.organisation_id,is_active=True).first():
            raise HTTPException(404,detail="Facility not found")
        q=q.filter(ERPStockLedger.facility_id==facility_id)
    rows=q.order_by(ERPStockLedger.item_id,ERPStockLedger.facility_id,ERPStockLedger.movement_date,ERPStockLedger.id).all()
    grouped={}
    for row in rows:
        key=(row.item_id,row.facility_id)
        grouped.setdefault(key,[]).append(row)
    result=[]
    for (item_id,site_id),movements in grouped.items():
        try:
            layers=replay_fifo_layers(movements)
        except ValueError as exc:
            raise HTTPException(409,detail=f"Stock history for item {item_id} needs reconciliation: {exc}")
        quantity,value=fifo_layer_totals(layers)
        item=db.query(ERPItem).filter_by(id=item_id,organisation_id=m.organisation_id).first()
        result.append({"item_id":item_id,"item_code":item.item_code,"name":item.name,
            "facility_id":site_id,"quantity_on_hand":str(quantity),"inventory_value":str(value),
            "valuation_method":"FIFO"})
    return result

@router.get("/journals")
def list_journals(m:Membership=Depends(require_org_permission("erp.read")),db:Session=Depends(get_db)):
    return db.query(ERPJournalEntry).filter_by(organisation_id=m.organisation_id).order_by(ERPJournalEntry.entry_date.desc(),ERPJournalEntry.id.desc()).limit(500).all()


@router.get("/party-balances")
def party_balances(m: Membership=Depends(require_org_permission("erp.read")), db: Session=Depends(get_db)):
    ar=func.coalesce(func.sum(case((ERPAccount.account_code=="1100",ERPJournalLine.debit-ERPJournalLine.credit),else_=0)),0)
    ap=func.coalesce(func.sum(case((ERPAccount.account_code=="2000",ERPJournalLine.credit-ERPJournalLine.debit),else_=0)),0)
    ca=func.coalesce(func.sum(case((ERPAccount.account_code=="2200",ERPJournalLine.credit-ERPJournalLine.debit),else_=0)),0)
    sa=func.coalesce(func.sum(case((ERPAccount.account_code=="1400",ERPJournalLine.debit-ERPJournalLine.credit),else_=0)),0)
    rows=db.query(ERPParty.id,ERPParty.party_code,ERPParty.name,ERPParty.party_type,
        ar.label("receivable"),ap.label("payable"),ca.label("customer_advance"),sa.label("supplier_advance"))
    rows=rows.outerjoin(ERPJournalLine,ERPJournalLine.party_id==ERPParty.id)
    rows=rows.outerjoin(ERPAccount,ERPAccount.id==ERPJournalLine.account_id)
    rows=rows.outerjoin(ERPJournalEntry,ERPJournalEntry.id==ERPJournalLine.journal_entry_id)
    rows=rows.filter(ERPParty.organisation_id==m.organisation_id).group_by(
        ERPParty.id,ERPParty.party_code,ERPParty.name,ERPParty.party_type).order_by(ERPParty.name)
    return [{"party_id":r.id,"party_code":r.party_code,"name":r.name,"party_type":r.party_type,
        "receivable":str(money(r.receivable or 0)),"payable":str(money(r.payable or 0)),
        "customer_advance":str(money(r.customer_advance or 0)),
        "supplier_advance":str(money(r.supplier_advance or 0))} for r in rows.all()]


@router.get("/payments")
def list_payments(m: Membership=Depends(require_org_permission("erp.read")), db: Session=Depends(get_db)):
    return db.query(ERPPayment).filter_by(organisation_id=m.organisation_id).order_by(
        ERPPayment.payment_date.desc(),ERPPayment.id.desc()).limit(500).all()


@router.post("/payments",status_code=201)
def create_payment(p: PaymentIn,m: Membership=Depends(require_org_permission("erp.manage")),
                   u: User=Depends(current_user),db: Session=Depends(get_db)):
    org=m.organisation_id
    fy=db.query(FinancialYear).filter(FinancialYear.organisation_id==org,FinancialYear.start_date<=p.payment_date,FinancialYear.end_date>=p.payment_date).first()
    if db.query(FinancialYear.id).filter_by(organisation_id=org).first() and (not fy or fy.is_closed):
        raise HTTPException(409,detail="Payment date is outside an open financial year")
    party=db.query(ERPParty).filter_by(id=p.party_id,organisation_id=org,is_active=True).first()
    expected="customer" if p.payment_type=="customer_receipt" else "supplier"
    if not party or party.party_type not in {expected,"both"}:
        raise HTTPException(422,detail=f"Select an active {expected} belonging to this organisation")
    if db.query(ERPPayment.id).filter_by(organisation_id=org,payment_no=p.payment_no).first():
        raise HTTPException(409,detail="Payment number already exists")
    bank=None
    if p.method!="cash":
        if not p.bank_account_id:
            raise HTTPException(422,detail="Select a bank account for non-cash payments")
        bank=db.query(ERPBankAccount).filter_by(id=p.bank_account_id,organisation_id=org,is_active=True).first()
        if not bank: raise HTTPException(422,detail="Bank account does not belong to this organisation")
    elif p.bank_account_id:
        raise HTTPException(422,detail="Cash payments should not specify a bank account")
    allocated=Decimal("0")
    checked=[]
    planned_by_doc={}
    for allocation in p.allocations:
        doc=db.query(ERPDocument).filter_by(id=allocation.document_id,organisation_id=org,party_id=party.id,status="posted").with_for_update().first()
        expected_doc="sales_invoice" if p.payment_type=="customer_receipt" else "purchase_bill"
        if not doc or doc.document_type!=expected_doc:
            raise HTTPException(422,detail="Allocation must reference a posted invoice/bill for this party")
        already=db.query(func.coalesce(func.sum(ERPPaymentAllocation.amount),0)).join(
            ERPPayment,ERPPayment.id==ERPPaymentAllocation.payment_id).filter(
            ERPPayment.organisation_id==org,ERPPaymentAllocation.document_id==doc.id).scalar() or 0
        amount=money(allocation.amount)
        planned=planned_by_doc.get(doc.id,Decimal("0.00"))+amount
        outstanding=money(Decimal(doc.grand_total)-Decimal(already))
        if planned>outstanding:
            raise HTTPException(422,detail=f"Allocation exceeds outstanding balance for {doc.document_no} ({outstanding})")
        planned_by_doc[doc.id]=planned
        allocated+=amount;checked.append((doc,amount))
    if allocated>money(p.amount):
        raise HTTPException(422,detail="Allocations cannot exceed payment amount")
    unallocated=money(p.amount)-allocated
    cash_account=_account(db,org,bank.account_code if bank else "1000")
    party_account=_account(db,org,"1100" if p.payment_type=="customer_receipt" else "2000")
    advance_account=_account(db,org,"2200" if p.payment_type=="customer_receipt" else "1400")
    journal=ERPJournalEntry(organisation_id=org,document_id=None,entry_no=f"PAY-{p.payment_no}",
        entry_date=p.payment_date,narration=f"{p.payment_type.replace('_',' ').title()} {p.payment_no}",
        posted_by_user_id=u.id)
    db.add(journal);db.flush()
    if p.payment_type=="customer_receipt":
        db.add(ERPJournalLine(journal_entry_id=journal.id,account_id=cash_account.id,debit=money(p.amount),credit=0,party_id=None))
        if allocated: db.add(ERPJournalLine(journal_entry_id=journal.id,account_id=party_account.id,debit=0,credit=allocated,party_id=party.id))
        if unallocated: db.add(ERPJournalLine(journal_entry_id=journal.id,account_id=advance_account.id,debit=0,credit=unallocated,party_id=party.id))
    else:
        if allocated: db.add(ERPJournalLine(journal_entry_id=journal.id,account_id=party_account.id,debit=allocated,credit=0,party_id=party.id))
        if unallocated: db.add(ERPJournalLine(journal_entry_id=journal.id,account_id=advance_account.id,debit=unallocated,credit=0,party_id=party.id))
        db.add(ERPJournalLine(journal_entry_id=journal.id,account_id=cash_account.id,debit=0,credit=money(p.amount),party_id=None))
    payment=ERPPayment(organisation_id=org,party_id=party.id,bank_account_id=bank.id if bank else None,
        journal_entry_id=journal.id,payment_no=p.payment_no,payment_type=p.payment_type,
        payment_date=p.payment_date,amount=money(p.amount),method=p.method,reference=p.reference,created_by_user_id=u.id)
    db.add(payment);db.flush()
    for doc,amount in checked:
        db.add(ERPPaymentAllocation(payment_id=payment.id,document_id=doc.id,amount=amount))
    _audit(db,m,u,"erp.payment.posted","erp_payment",payment.id,
        f"Posted {p.payment_type} {p.payment_no} for {money(p.amount)}; allocated {money(allocated)}")
    db.commit();db.refresh(payment)
    return {"payment":payment,"allocated_amount":money(allocated),"unallocated_amount":money(p.amount)-money(allocated)}


@router.get("/bank-accounts")
def list_bank_accounts(m:Membership=Depends(require_org_permission("erp.read")),db:Session=Depends(get_db)):
    return db.query(ERPBankAccount).filter_by(organisation_id=m.organisation_id,is_active=True).order_by(ERPBankAccount.account_code).all()


@router.post("/bank-accounts",status_code=201)
def create_bank_account(p:BankAccountIn,m:Membership=Depends(require_org_permission("erp.manage")),
                        u:User=Depends(current_user),db:Session=Depends(get_db)):
    if db.query(ERPBankAccount.id).filter_by(organisation_id=m.organisation_id,account_code=p.account_code).first() or db.query(ERPAccount.id).filter_by(organisation_id=m.organisation_id,account_code=p.account_code).first():
        raise HTTPException(409,detail="Bank ledger code already exists")
    ledger=ERPAccount(organisation_id=m.organisation_id,account_code=p.account_code,
        name=f"{p.bank_name} — {p.account_label}",account_type="asset",is_system=False)
    db.add(ledger);db.flush()
    row=ERPBankAccount(organisation_id=m.organisation_id,ledger_account_id=ledger.id,**p.model_dump())
    db.add(row);db.flush()
    _audit(db,m,u,"erp.bank_account.created","erp_bank_account",row.id,f"Created bank account {p.account_label}")
    db.commit();db.refresh(row);return row


@router.get("/bank-statement-lines")
def list_bank_statement_lines(bank_account_id:int|None=None,m:Membership=Depends(require_org_permission("erp.read")),
                              db:Session=Depends(get_db)):
    q=db.query(ERPBankStatementLine).filter_by(organisation_id=m.organisation_id)
    if bank_account_id is not None:q=q.filter_by(bank_account_id=bank_account_id)
    return q.order_by(ERPBankStatementLine.transaction_date.desc(),ERPBankStatementLine.id.desc()).limit(1000).all()


@router.post("/bank-statement-lines",status_code=201)
def import_bank_statement_line(p:BankStatementLineIn,m:Membership=Depends(require_org_permission("erp.manage")),
                               u:User=Depends(current_user),db:Session=Depends(get_db)):
    bank=db.query(ERPBankAccount).filter_by(id=p.bank_account_id,organisation_id=m.organisation_id,is_active=True).first()
    if not bank:raise HTTPException(422,detail="Bank account does not belong to this organisation")
    row=ERPBankStatementLine(organisation_id=m.organisation_id,**p.model_dump())
    db.add(row);db.flush()
    _audit(db,m,u,"erp.bank_statement.imported","erp_bank_statement_line",row.id,
        f"Imported {p.direction} statement line {p.amount}")
    db.commit();db.refresh(row);return row


@router.post("/bank-statement-lines/{line_id}/reconcile")
def reconcile_bank_statement_line(line_id:int,payment_id:int,m:Membership=Depends(require_org_permission("erp.manage")),
                                  u:User=Depends(current_user),db:Session=Depends(get_db)):
    line=db.query(ERPBankStatementLine).filter_by(id=line_id,organisation_id=m.organisation_id).with_for_update().first()
    if not line:raise HTTPException(404,detail="Statement line not found")
    if line.reconciled_payment_id:raise HTTPException(409,detail="Statement line is already reconciled")
    payment=db.query(ERPPayment).filter_by(id=payment_id,organisation_id=m.organisation_id).first()
    if not payment:raise HTTPException(404,detail="Payment not found")
    if payment.bank_account_id!=line.bank_account_id:
        raise HTTPException(422,detail="Payment and statement line belong to different bank accounts")
    expected_direction="credit" if payment.payment_type=="customer_receipt" else "debit"
    if line.direction!=expected_direction or money(line.amount)!=money(payment.amount):
        raise HTTPException(422,detail="Statement direction or amount does not match the payment")
    if line.transaction_date<payment.payment_date:
        raise HTTPException(422,detail="Statement transaction date cannot precede payment date")
    line.reconciled_payment_id=payment.id
    _audit(db,m,u,"erp.bank_statement.reconciled","erp_bank_statement_line",line.id,
        f"Matched statement line to payment {payment.payment_no}")
    db.commit();db.refresh(line);return line


@router.get("/bank-reconciliation-summary")
def bank_reconciliation_summary(m:Membership=Depends(require_org_permission("erp.read")),db:Session=Depends(get_db)):
    rows=db.query(ERPBankStatementLine.bank_account_id,
        func.count(ERPBankStatementLine.id).label("line_count"),
        func.sum(ERPBankStatementLine.amount).label("gross_amount"),
        func.sum(case((ERPBankStatementLine.reconciled_payment_id.is_not(None),1),else_=0)).label("matched_count")
    ).filter_by(organisation_id=m.organisation_id).group_by(ERPBankStatementLine.bank_account_id).all()
    return [{"bank_account_id":r.bank_account_id,"line_count":r.line_count,
        "matched_count":int(r.matched_count or 0),"unmatched_count":r.line_count-int(r.matched_count or 0),
        "statement_gross":str(money(r.gross_amount or 0))} for r in rows]
