"use client";
import {useState} from "react";

const nav=["Dashboard","Patients","Appointments","Laboratory","Hospital","Transactions","Billing","Inventory","HR","Analytics","Audit & Logs","Settings"];
const modules=[
  ["PMS","Patient Management","MPI, registration, encounters, appointments and clinical timeline."],
  ["LMIS","Laboratory Management","Orders, specimens, analyzers, validation and report release."],
  ["HMS","Hospital Management","Admissions, wards, beds, nursing workflow and discharge."],
  ["TMS","Transaction Management","Authorisation, services, packages, claims and settlement."],
  ["Billing","Billing & Finance","Invoices, payments, receivables, refunds and reporting."],
  ["Inventory","Inventory & Pharmacy","Stock, batches, expiry, purchase, issue and reorder controls."]
];
const patients=[
  ["NX-0001842","Aarav Khan","42 / M","Kulgam DC","01 Oct 2026","Active"],
  ["NX-0001843","Sana Mir","31 / F","Kulgam DC","01 Oct 2026","Active"],
  ["NX-0001844","Rohan Bhat","58 / M","City Branch","30 Sep 2026","Follow-up"],
  ["NX-0001845","Mehak Jan","26 / F","Kulgam DC","30 Sep 2026","Active"],
  ["NX-0001846","Irfan Ahmad","67 / M","City Branch","29 Sep 2026","Active"]
];
const labs=[
  ["LAB-02681","Aarav Khan","CBC","EDTA","Routine","Processing"],
  ["LAB-02682","Sana Mir","LFT","Serum","Urgent","Validation"],
  ["LAB-02683","Rohan Bhat","HbA1c","EDTA","Routine","Collected"],
  ["LAB-02684","Mehak Jan","Lipid","Serum","Routine","Reported"],
  ["LAB-02685","Irfan Ahmad","KFT","Serum","Urgent","Processing"]
];

function Pill({children,type=""}){return <span className={"pill "+type}>{children}</span>}
function Kpi({label,value,tag,type=""}){return <div className="kpi"><div className="kpi-label">{label}</div><div className="kpi-value">{value}</div><Pill type={type}>{tag}</Pill></div>}
function Panel({title,children,action}){return <section className="panel"><div className="table-head" style={{padding:0,marginBottom:12}}><h3>{title}</h3>{action}</div>{children}</section>}
function DataTable({headers,rows}){return <table className="table"><thead><tr>{headers.map(h=><th key={h}>{h}</th>)}</tr></thead><tbody>{rows.map((r,i)=><tr key={i}>{r.map((v,j)=><td key={j}>{j===r.length-1?<Pill type={v==="Active"||v==="Reported"||v==="Connected"?"green":v==="Urgent"||v==="Pending"?"orange":""}>{v}</Pill>:v}</td>)}</tr>)}</tbody></table>}

export default function Home(){
 const [active,setActive]=useState("Dashboard");
 const [facility,setFacility]=useState("Kulgam Diagnostic Centre");
 const [query,setQuery]=useState("");
 const title=active==="Dashboard"?"Organisation Dashboard":active;
 const subtitle=active==="Dashboard"?"Unified operational view across facilities and departments.":"Nexa Management operational workspace.";
 const filtered=patients.filter(p=>p.join(" ").toLowerCase().includes(query.toLowerCase()));

 return <div className="nexa-app">
  <aside className="sidebar">
   <div className="brand"><strong>NEXA</strong><span>SPRINGNEXA PRIVATE LIMITED</span></div>
   <nav className="nav">{nav.map(item=><button key={item} className={active===item?"active":""} onClick={()=>setActive(item)}>{item}</button>)}</nav>
   <div className="sidebar-footer">Multi-organisation • Multi-tenant<br/>AI gateway: OFF by default</div>
  </aside>
  <main className="main">
   <div className="topbar">
    <div><div className="eyebrow">NEXA MANAGEMENT / {active.toUpperCase()}</div><h1 className="title">{title}</h1><div className="muted" style={{fontSize:11,marginTop:4}}>{subtitle}</div></div>
    <div className="actions">
      <select className="control" value={facility} onChange={e=>setFacility(e.target.value)}><option>Kulgam Diagnostic Centre</option><option>City Branch</option><option>Mobile Unit</option></select>
      <input className="search" placeholder="Search patients, orders, invoices..." value={query} onChange={e=>setQuery(e.target.value)}/>
      <button className="avatar">Admin</button>
    </div>
   </div>

   {active==="Dashboard" && <>
    <div className="grid4">
      <Kpi label="Patients Today" value="126" tag="+14%" />
      <Kpi label="Lab Orders" value="84" tag="+9" type="purple"/>
      <Kpi label="Admissions" value="18" tag="6 active" type="orange"/>
      <Kpi label="Revenue Today" value="₹4.82L" tag="+12.4%" type="green"/>
    </div>
    <div className="panel-grid">
      <Panel title="Patient / Order Volume"><div className="chart">{[42,56,48,72,68,88,94,84].map((v,i)=><div key={i} className={"bar "+(i===6?"active":"")} style={{height:(v/100*120)+"px"}}/>)}</div></Panel>
      <Panel title="System Services">{["API Gateway","Database","Notifications","File Storage"].map(x=><div className="setting-row" key={x}><span>{x}</span><span><i className="status-dot"/>Operational</span></div>)}</Panel>
    </div>
    <div className="table-panel"><div className="table-head"><h3>Facility Operations</h3><Pill>Live</Pill></div><DataTable headers={["Facility","Patients","Lab Orders","Admissions","Revenue"]} rows={[["Kulgam Main","68","42","9","₹2.41L"],["City Branch","41","29","6","₹1.72L"],["Mobile Unit","17","13","3","₹0.69L"]]}/></div>
   </>}

   {active==="Patients" && <><div className="grid4"><Kpi label="Registered Patients" value="18,426" tag="+126"/><Kpi label="Active Today" value="126" tag="Live" type="green"/><Kpi label="Duplicates Flagged" value="7" tag="Review" type="orange"/><Kpi label="Consent Coverage" value="96.8%" tag="+1.2%" type="green"/></div><div className="table-panel"><div className="table-head"><h3>Patient Registry</h3><Pill>MPI Protected</Pill></div><DataTable headers={["UHID","Patient","Age/Sex","Facility","Last Visit","Status"]} rows={filtered}/></div></>}

   {active==="Laboratory" && <><div className="grid4"><Kpi label="Orders Today" value="84" tag="+11"/><Kpi label="Samples" value="79" tag="94%" type="purple"/><Kpi label="In Process" value="23" tag="12 urgent" type="orange"/><Kpi label="Reports Ready" value="56" tag="67%" type="green"/></div><div className="table-panel"><div className="table-head"><h3>Laboratory Work Queue</h3><Pill>Analyzer Online</Pill></div><DataTable headers={["Lab No.","Patient","Panel","Sample","Priority","Status"]} rows={labs}/></div></>}

   {["Hospital","Transactions","Billing","Inventory","HR","Analytics","Audit & Logs","Appointments"].includes(active) && <ModuleView active={active}/>}
   {active==="Settings" && <Settings/>}
  </main>
 </div>
}

function ModuleView({active}){
 const data={
  Hospital:[["Occupied Beds","78","+6"],["Available","24","Live"],["Pending Admission","7","Open"],["Discharge Today","11","Today"]],
  Transactions:[["Open Cases","142","+18"],["Authorisations","38","12 pending"],["Services","684","This month"],["Settlement","₹28.4L","92% closed"]],
  Billing:[["Invoices Today","74","+9"],["Collected","₹6.82L","+7.4%"],["Receivables","₹18.3L","-3.1%"],["Refunds","₹42K","8 cases"]],
  Inventory:[["SKUs","4,826","+126"],["Low Stock","37","Attention"],["Expiring <30d","19","Review"],["Stock Value","₹48.2L","+4.8%"]],
  HR:[["Employees","284","+12"],["Present","251","88.4%"],["On Leave","18","Today"],["Open Roles","9","Recruitment"]],
  Analytics:[["Monthly Visits","12,482","+8.2%"],["Revenue","₹1.84Cr","+11.4%"],["Lab TAT","2h 18m","-12m"],["Collection Rate","94.2%","+2.1%"]],
  "Audit & Logs":[["Events Today","2,481","Recorded"],["Failed Logins","8","Review"],["Permission Changes","12","Audited"],["API Rotations","4","Secure"]],
  Appointments:[["Appointments","186","Today"],["Checked In","124","67%"],["Waiting","18","Live"],["No Shows","7","3.8%"]]
 }[active];
 return <><div className="grid4">{data.map((x,i)=><Kpi key={x[0]} label={x[0]} value={x[1]} tag={x[2]} type={i===1?"green":i===2?"orange":""}/>)}</div><div className="panel-grid"><Panel title={active+" Overview"}><div className="chart">{[35,48,42,64,57,78,72,88].map((v,i)=><div key={i} className={"bar "+(i===7?"active":"")} style={{height:(v/100*120)+"px"}}/>)}</div></Panel><Panel title="Workflow Status">{["Requested","In Progress","Validation","Completed"].map((x,i)=><div className="setting-row" key={x}><span>{x}</span><Pill type={i===3?"green":i===2?"orange":""}>{[12,23,18,67][i]}</Pill></div>)}</Panel></div><div className="table-panel"><div className="table-head"><h3>Recent {active} Activity</h3><Pill>Live</Pill></div><DataTable headers={["Reference","Entity","Owner","Updated","Status"]} rows={[["NX-10982","Aarav Khan","Admin","17:02","Active"],["NX-10983","Sana Mir","Finance","16:58","Pending"],["NX-10984","Rohan Bhat","Clinical","16:44","Active"],["NX-10985","Mehak Jan","Lab","16:31","Reported"]]}/></div></>
}
function Settings(){return <><div className="grid4"><Kpi label="Cloudflare" value="Protected" tag="Live" type="green"/><Kpi label="Oracle Cloud" value="Connected" tag="Live" type="green"/><Kpi label="PostgreSQL" value="Healthy" tag="Live" type="green"/><Kpi label="Notifications" value="Configured" tag="Live"/></div><div className="settings" style={{marginTop:14}}><Panel title="Integration Registry">{["REST API","Webhooks","HL7 / ASTM","Email / SMS"].map(x=><div className="setting-row" key={x}><span>{x}</span><span><i className="status-dot"/>Connected</span></div>)}</Panel><Panel title="Release Controls">{["CI / CD","Database migrations","Health checks","Backups","Rollback","Feature flags"].map(x=><div className="setting-row" key={x}><span>{x}</span><Pill type="green">Enabled</Pill></div>)}</Panel></div><div className="notice" style={{marginTop:14}}><b>Security baseline:</b> tenant isolation, least-privilege RBAC, JWT sessions, audit logging, encrypted secrets and AI OFF by default. Production credentials are never stored in source code.</div></>}
