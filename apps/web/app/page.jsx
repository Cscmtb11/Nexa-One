export default function Home() {
  const modules = ["PMS","HMS","LMIS","TMS","Billing","Inventory"];
  return <main style={{maxWidth:1100,margin:"0 auto",padding:"64px 24px"}}>
    <p style={{letterSpacing:2,fontWeight:700,color:"#1d5d7a"}}>SPRINGNEXA PRIVATE LIMITED</p>
    <h1 style={{fontSize:48}}>Nexa Management</h1>
    <p style={{fontSize:20,color:"#4a5560"}}>Multi-organisation, multi-tenant healthcare operations platform.</p>
    <div style={{display:"grid",gap:12,gridTemplateColumns:"repeat(auto-fit,minmax(180px,1fr))"}}>
      {modules.map(m=><div key={m} style={{background:"#fff",padding:20,borderRadius:12}}><strong>{m}</strong></div>)}
    </div>
  </main>;
}
