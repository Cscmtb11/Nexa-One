from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session
from ..db import get_db
from ..dependencies import current_user, require_org_permission
from ..models import (
    AuditEvent, ERPAccount, ERPDocument, ERPDocumentLine, ERPItem, ERPJournalEntry,
    ERPJournalLine, ERPParty, ERPStockLedger, ERPTaxCode, FinancialYear, Facility,
    Membership, User,
)

router = APIRouter(prefix="/v1/erp", tags=["shared ERP"])
CENT = Decimal("0.01")

def money(value):
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)

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
    doc=ERPDocument(organisation_id=org,facility_id=p.facility_id,party_id=party.id,document_type=p.document_type,
        document_no=p.document_no,issue_date=p.issue_date,due_date=p.due_date,place_of_supply_state=p.place_of_supply_state,
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
        db.add(ERPDocumentLine(document_id=doc.id,item_id=item.id,tax_code_id=tax.id if tax else None,
            description=line.description or item.name,quantity=line.quantity,unit_price=line.unit_price,
            discount_amount=discount,tax_rate=rate,taxable_amount=taxable,tax_amount=tax_amount,line_total=taxable+tax_amount))
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
    tax_account=_account(db,org,"1300" if inbound else "2100")
    journal=ERPJournalEntry(organisation_id=org,document_id=doc.id,entry_no=f"ERP-{doc.document_no}",entry_date=doc.issue_date,
        narration=f"{doc.document_type.replace('_',' ').title()} {doc.document_no}",posted_by_user_id=u.id)
    db.add(journal);db.flush()
    def jl(account,debit=0,credit=0):
        db.add(ERPJournalLine(journal_entry_id=journal.id,account_id=account.id,debit=money(debit),credit=money(credit),party_id=party.id))
    if inbound:
        jl(base_account,debit=subtotal);jl(tax_account,debit=tax_total);jl(party_account,credit=grand)
    else:
        jl(party_account,debit=grand);jl(base_account,credit=subtotal);jl(tax_account,credit=tax_total)
    for line in lines:
        item=db.query(ERPItem).filter_by(id=line.item_id,organisation_id=org).first()
        if item.track_stock and item.item_type=="goods":
            current=db.query(func.coalesce(func.sum(ERPStockLedger.quantity_in-ERPStockLedger.quantity_out),0)).filter(
                ERPStockLedger.organisation_id==org,ERPStockLedger.item_id==item.id,
                ERPStockLedger.facility_id==doc.facility_id).scalar() or 0
            if not inbound and Decimal(current)<Decimal(line.quantity):
                db.rollback();raise HTTPException(409,detail=f"Insufficient stock for {item.item_code}; available {current}")
            db.add(ERPStockLedger(organisation_id=org,facility_id=doc.facility_id,item_id=item.id,document_id=doc.id,
                movement_date=doc.issue_date,quantity_in=line.quantity if inbound else 0,
                quantity_out=0 if inbound else line.quantity,unit_cost=line.unit_price))
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

@router.get("/journals")
def list_journals(m:Membership=Depends(require_org_permission("erp.read")),db:Session=Depends(get_db)):
    return db.query(ERPJournalEntry).filter_by(organisation_id=m.organisation_id).order_by(ERPJournalEntry.entry_date.desc(),ERPJournalEntry.id.desc()).limit(500).all()
