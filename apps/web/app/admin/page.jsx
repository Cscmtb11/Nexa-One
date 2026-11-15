"use client";

import {useCallback, useEffect, useMemo, useState} from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const tabs = ["Legal entities", "GST registrations", "Financial years", "Users & access", "Role permissions", "Organisation settings"];
const emptyEntity = {code:"",legal_name:"",trade_name:"",pan:"",constitution:"other",address_line1:"",city:"",district:"",state_code:"",state_name:"",pincode:"",country:"IN"};
const emptyGst = {legal_entity_id:"",facility_id:"",gstin:"",registration_type:"regular",state_code:"",effective_from:"",is_primary:false};
const emptyYear = {name:"",start_date:"",end_date:"",is_current:false};

function Field({label,children}) {
  return <label className="admin-field"><span>{label}</span>{children}</label>;
}
function DataGrid({columns,rows}) {
  if (!rows?.length) return <div className="admin-empty">No records found. Add the first record using the form.</div>;
  return <div className="admin-table-wrap"><table className="admin-table"><thead><tr>{columns.map(c=><th key={c.key}>{c.label}</th>)}</tr></thead><tbody>{rows.map((row,i)=><tr key={row.id || row.user_id || row.key || i}>{columns.map(c=><td key={c.key}>{String(row[c.key] ?? "—")}</td>)}</tr>)}</tbody></table></div>;
}

export default function TenantAdminPage(){
  const [token,setToken]=useState("");
  const [email,setEmail]=useState("");
  const [password,setPassword]=useState("");
  const [organisations,setOrganisations]=useState([]);
  const [orgId,setOrgId]=useState("");
  const [active,setActive]=useState(tabs[0]);
  const [data,setData]=useState({entities:[],gst:[],years:[],users:[],settings:{}});
  const [facilities,setFacilities]=useState([]);
  const [permissionData,setPermissionData]=useState({catalog:[],roles:{}});
  const [permissionRole,setPermissionRole]=useState("manager");
  const [selectedPermissions,setSelectedPermissions]=useState([]);
  const [entity,setEntity]=useState(emptyEntity);
  const [gst,setGst]=useState(emptyGst);
  const [year,setYear]=useState(emptyYear);
  const [invite,setInvite]=useState({email:"",role:"member"});
  const [invitationToken,setInvitationToken]=useState("");
  const [setting,setSetting]=useState({key:"timezone",value:"Asia/Kolkata"});
  const [message,setMessage]=useState("");
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);
  const [ready,setReady]=useState(false);

  const request = useCallback(async(path, options={})=>{
    const headers={"Content-Type":"application/json",...(token?{Authorization:"Bearer "+token}:{}),...(orgId?{"X-Org-Id":String(orgId)}:{}),...(options.headers||{})};
    const response=await fetch(API+path,{...options,headers});
    const body=await response.json().catch(()=>({}));
    if(!response.ok) throw new Error(body.detail || "Request failed ("+response.status+")");
    return body;
  },[token,orgId]);

  const loadOrganisations=useCallback(async(authToken)=>{
    const response=await fetch(API+"/v1/organisations",{headers:{Authorization:"Bearer "+authToken}});
    const body=await response.json().catch(()=>[]);
    if(!response.ok) throw new Error(body.detail || "Could not load organisations");
    setOrganisations(body);
    if(body.length) setOrgId(String(body[0].id));
  },[]);

  useEffect(()=>{
    const saved=typeof window!=="undefined"?sessionStorage.getItem("nexa_admin_token"):"";
    if(saved){setToken(saved);loadOrganisations(saved).then(()=>setReady(true)).catch(()=>sessionStorage.removeItem("nexa_admin_token"));}
  },[loadOrganisations]);

  const loadData=useCallback(async()=>{
    if(!token || !orgId) return;
    setBusy(true);setError("");
    try{
      const [entities,gstRows,years,users,settings,facilityRows,permissionRows]=await Promise.all([
        request("/v1/tenant/legal-entities"),
        request("/v1/tenant/gst-registrations"),
        request("/v1/tenant/financial-years"),
        request("/v1/tenant/users"),
        request("/v1/tenant/settings"),
        request("/v1/facilities"),
        request("/v1/tenant/permissions")
      ]);
      setData({entities,gst:gstRows,years,users,settings});
      setFacilities(facilityRows);
      setPermissionData(permissionRows);
      setSelectedPermissions(permissionRows.roles?.[permissionRole] || []);
    }catch(e){setError(e.message);}
    finally{setBusy(false);}
  },[token,orgId,request]);

  useEffect(()=>{if(ready && token && orgId) loadData();},[ready,token,orgId,loadData]);

  async function login(e){
    e.preventDefault();setBusy(true);setError("");setMessage("");
    try{
      const response=await fetch(API+"/v1/auth/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({email,password})});
      const body=await response.json().catch(()=>({}));
      if(!response.ok) throw new Error(body.detail || "Login failed");
      sessionStorage.setItem("nexa_admin_token",body.access_token);
      setToken(body.access_token);
      await loadOrganisations(body.access_token);
      setReady(true);setMessage("Signed in successfully.");
    }catch(e){setError(e.message);}
    finally{setBusy(false);}
  }

  function logout(){sessionStorage.removeItem("nexa_admin_token");setToken("");setOrganisations([]);setOrgId("");setReady(false);setData({entities:[],gst:[],years:[],users:[],settings:{}});}

  async function submit(path,payload,success,reset){
    setBusy(true);setError("");setMessage("");
    try{const result=await request(path,{method:"POST",body:JSON.stringify(payload)});if(result.invitation_token)setInvitationToken(result.invitation_token);setMessage(success);if(reset)reset();await loadData();}
    catch(e){setError(e.message);}
    finally{setBusy(false);}
  }

  useEffect(()=>{setSelectedPermissions(permissionData.roles?.[permissionRole] || []);},[permissionRole,permissionData]);

  const currentOrg=useMemo(()=>organisations.find(o=>String(o.id)===String(orgId)),[organisations,orgId]);

  if(!token || !ready) return <main className="admin-login-shell"><form className="admin-login" onSubmit={login}><div className="admin-brand">NEXA <span>SPRINGNEXA PRIVATE LIMITED</span></div><h1>Tenant administration</h1><p>Sign in with your NEXA account to manage organisation registrations, branches and access.</p><Field label="Account email"><input type="email" value={email} onChange={e=>setEmail(e.target.value)} required autoComplete="username"/></Field><Field label="Password"><input type="password" value={password} onChange={e=>setPassword(e.target.value)} required autoComplete="current-password"/></Field>{error&&<div className="admin-alert error">{error}</div>}<button className="admin-primary" disabled={busy}>{busy?"Signing in…":"Sign in"}</button><a href="/" className="admin-back">← Back to NEXA workspace</a></form></main>;

  return <main className="admin-shell">
    <header className="admin-top"><div><div className="admin-brand">NEXA <span>PLATFORM ADMINISTRATION</span></div><h1>Organisation & compliance</h1><p>Configure legal entities, GST registrations, financial years and organisation access.</p></div><div className="admin-top-actions"><select value={orgId} onChange={e=>setOrgId(e.target.value)}>{organisations.map(o=><option key={o.id} value={o.id}>{o.name} · {o.role}</option>)}</select><button className="admin-secondary" onClick={logout}>Sign out</button></div></header>
    <nav className="admin-tabs">{tabs.map(t=><button key={t} className={active===t?"selected":""} onClick={()=>setActive(t)}>{t}</button>)}</nav>
    {message&&<div className="admin-alert success">{message}</div>}{error&&<div className="admin-alert error">{error}</div>}
    {busy&&<div className="admin-loading">Loading / saving organisation data…</div>}
    {active==="Legal entities"&&<div className="admin-columns"><section className="admin-card"><h2>Add legal entity</h2><p>Register the legal owner for one or more facilities and GST registrations.</p><form onSubmit={e=>{e.preventDefault();submit("/v1/tenant/legal-entities",entity,"Legal entity created.",()=>setEntity(emptyEntity));}} className="admin-form">
      <Field label="Entity code"><input value={entity.code} onChange={e=>setEntity({...entity,code:e.target.value})} required placeholder="NEXA-JK"/></Field>
      <Field label="Legal name"><input value={entity.legal_name} onChange={e=>setEntity({...entity,legal_name:e.target.value})} required/></Field>
      <Field label="Trade name"><input value={entity.trade_name} onChange={e=>setEntity({...entity,trade_name:e.target.value})}/></Field>
      <Field label="PAN"><input maxLength="10" value={entity.pan} onChange={e=>setEntity({...entity,pan:e.target.value.toUpperCase()})} placeholder="ABCDE1234F"/></Field>
      <Field label="Constitution"><select value={entity.constitution} onChange={e=>setEntity({...entity,constitution:e.target.value})}><option value="proprietorship">Proprietorship</option><option value="partnership">Partnership</option><option value="llp">LLP</option><option value="private_limited">Private Limited</option><option value="public_limited">Public Limited</option><option value="trust">Trust</option><option value="society">Society</option><option value="other">Other</option></select></Field>
      <Field label="Address"><input value={entity.address_line1} onChange={e=>setEntity({...entity,address_line1:e.target.value})}/></Field>
      <Field label="City"><input value={entity.city} onChange={e=>setEntity({...entity,city:e.target.value})}/></Field>
      <Field label="District"><input value={entity.district} onChange={e=>setEntity({...entity,district:e.target.value})}/></Field>
      <Field label="State code"><input maxLength="2" value={entity.state_code} onChange={e=>setEntity({...entity,state_code:e.target.value})} placeholder="01"/></Field>
      <Field label="State"><input value={entity.state_name} onChange={e=>setEntity({...entity,state_name:e.target.value})}/></Field>
      <Field label="PIN code"><input value={entity.pincode} onChange={e=>setEntity({...entity,pincode:e.target.value})}/></Field>
      <button className="admin-primary" disabled={busy}>Save legal entity</button>
    </form></section><section className="admin-card"><h2>Registered legal entities</h2><DataGrid columns={[{key:"code",label:"Code"},{key:"legal_name",label:"Legal name"},{key:"pan",label:"PAN"},{key:"constitution",label:"Type"},{key:"state_name",label:"State"}]} rows={data.entities}/></section></div>}
    {active==="GST registrations"&&<div className="admin-columns"><section className="admin-card"><h2>Add GST registration</h2><p>GSTIN is validated for format, state code and matching PAN where available.</p><form className="admin-form" onSubmit={e=>{e.preventDefault();submit("/v1/tenant/gst-registrations",{...gst,legal_entity_id:Number(gst.legal_entity_id),facility_id:gst.facility_id?Number(gst.facility_id):null,effective_from:gst.effective_from||null},"GST registration saved.",()=>setGst(emptyGst));}}>
      <Field label="Legal entity"><select required value={gst.legal_entity_id} onChange={e=>setGst({...gst,legal_entity_id:e.target.value})}><option value="">Select entity</option>{data.entities.map(x=><option key={x.id} value={x.id}>{x.legal_name}</option>)}</select></Field>
      <Field label="Facility (optional)"><select value={gst.facility_id} onChange={e=>setGst({...gst,facility_id:e.target.value})}><option value="">Organisation-wide</option>{facilities.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select></Field>
      <Field label="GSTIN"><input maxLength="15" value={gst.gstin} onChange={e=>setGst({...gst,gstin:e.target.value.toUpperCase()})} required placeholder="15-character GSTIN"/></Field>
      <Field label="State code"><input maxLength="2" value={gst.state_code} onChange={e=>setGst({...gst,state_code:e.target.value})} required placeholder="01"/></Field>
      <Field label="Registration type"><select value={gst.registration_type} onChange={e=>setGst({...gst,registration_type:e.target.value})}><option value="regular">Regular</option><option value="composition">Composition</option><option value="casual">Casual taxable person</option><option value="non_resident">Non-resident taxable person</option><option value="sez">SEZ</option></select></Field>
      <Field label="Effective from"><input type="date" value={gst.effective_from} onChange={e=>setGst({...gst,effective_from:e.target.value})}/></Field>
      <label className="admin-check"><input type="checkbox" checked={gst.is_primary} onChange={e=>setGst({...gst,is_primary:e.target.checked})}/> Set as primary GST registration</label>
      <button className="admin-primary" disabled={busy||!data.entities.length}>Save GST registration</button>
    </form></section><section className="admin-card"><h2>GST registrations</h2><DataGrid columns={[{key:"gstin",label:"GSTIN"},{key:"legal_entity_id",label:"Entity ID"},{key:"state_code",label:"State"},{key:"registration_type",label:"Type"},{key:"is_primary",label:"Primary"},{key:"is_active",label:"Active"}]} rows={data.gst}/></section></div>}
    {active==="Financial years"&&<div className="admin-columns"><section className="admin-card"><h2>Create financial year</h2><p>Financial years cannot overlap. Only one open year can be current.</p><form className="admin-form" onSubmit={e=>{e.preventDefault();submit("/v1/tenant/financial-years",year,"Financial year created.",()=>setYear(emptyYear));}}>
      <Field label="Name"><input value={year.name} onChange={e=>setYear({...year,name:e.target.value})} required placeholder="FY 2026-27"/></Field>
      <Field label="Start date"><input type="date" value={year.start_date} onChange={e=>setYear({...year,start_date:e.target.value})} required/></Field>
      <Field label="End date"><input type="date" value={year.end_date} onChange={e=>setYear({...year,end_date:e.target.value})} required/></Field>
      <label className="admin-check"><input type="checkbox" checked={year.is_current} onChange={e=>setYear({...year,is_current:e.target.checked})}/> Make current financial year</label>
      <button className="admin-primary" disabled={busy}>Create financial year</button>
    </form></section><section className="admin-card"><h2>Financial year register</h2><DataGrid columns={[{key:"name",label:"Year"},{key:"start_date",label:"From"},{key:"end_date",label:"To"},{key:"is_current",label:"Current"},{key:"is_closed",label:"Closed"}]} rows={data.years}/></section></div>}
    {active==="Users & access"&&<div className="admin-columns"><section className="admin-card"><h2>Invite existing NEXA user</h2><p>The invited person must already have a NEXA account. Share the one-time token securely; email delivery integration is a later step.</p><form className="admin-form" onSubmit={e=>{e.preventDefault();submit("/v1/tenant/invitations",invite,"Invitation created. Copy its token from the response in the API client or activity logs.",()=>setInvite({email:"",role:"member"}));}}>
      <Field label="User email"><input type="email" value={invite.email} onChange={e=>setInvite({...invite,email:e.target.value})} required/></Field>
      <Field label="Role"><select value={invite.role} onChange={e=>setInvite({...invite,role:e.target.value})}>{["member","manager","accountant","clinician","technician","admin"].map(r=><option key={r}>{r}</option>)}</select></Field>
      <button className="admin-primary" disabled={busy}>Create invitation</button>
    </form>{invitationToken&&<div className="admin-note"><b>One-time invitation token</b><p>Share this token privately with the invited user. It is shown only now.</p><code>{invitationToken}</code></div>}<div className="admin-note">Only the organisation owner can invite an admin or change role permissions. Invitation tokens expire after seven days.</div></section><section className="admin-card"><h2>Organisation users</h2><div className="admin-table-wrap"><table className="admin-table"><thead><tr><th>User</th><th>Role</th><th>Action</th></tr></thead><tbody>{data.users.map(u=><tr key={u.user_id}><td><b>{u.full_name}</b><br/>{u.email}</td><td>{u.role}</td><td>{u.role==="owner"?<span>Protected owner</span>:<div className="admin-user-actions"><select aria-label={"Role for "+u.email} defaultValue={u.role} onChange={e=>{const next=e.target.value;setBusy(true);request("/v1/tenant/users/"+u.user_id+"/role",{method:"PUT",body:JSON.stringify({role:next})}).then(()=>{setMessage("User role updated.");loadData();}).catch(e=>setError(e.message)).finally(()=>setBusy(false));}}>{["admin","manager","accountant","clinician","technician","member"].map(r=><option key={r}>{r}</option>)}</select><button className="admin-danger" onClick={()=>{if(!window.confirm("Remove "+u.email+" from this organisation?"))return;setBusy(true);request("/v1/tenant/users/"+u.user_id,{method:"DELETE"}).then(()=>{setMessage("User removed from organisation.");loadData();}).catch(e=>setError(e.message)).finally(()=>setBusy(false));}}>Remove</button></div>}</td></tr>)}</tbody></table></div></section></div>}
    {active==="Role permissions"&&<div className="admin-columns"><section className="admin-card"><h2>Role permission matrix</h2><p>Choose the capabilities available to each organisation role. Only the organisation owner can save changes.</p><Field label="Role"><select value={permissionRole} onChange={e=>setPermissionRole(e.target.value)}>{["admin","manager","accountant","clinician","technician","member"].map(r=><option key={r}>{r}</option>)}</select></Field><div className="permission-list">{permissionData.catalog.map(p=><label className="admin-check permission-check" key={p.code}><input type="checkbox" checked={selectedPermissions.includes(p.code)} onChange={e=>setSelectedPermissions(old=>e.target.checked?[...old,p.code]:old.filter(x=>x!==p.code))}/><span><b>{p.code}</b><small>{p.description}</small></span></label>)}</div><button className="admin-primary" disabled={busy} onClick={()=>{setBusy(true);setError("");request("/v1/tenant/permissions/"+permissionRole,{method:"PUT",body:JSON.stringify({permission_codes:selectedPermissions})}).then(()=>{setMessage("Role permissions updated.");loadData();}).catch(e=>setError(e.message)).finally(()=>setBusy(false));}}>Save role permissions</button></section><section className="admin-card"><h2>Access control guidance</h2><div className="admin-note">Owner retains full control. Admin cannot receive the organisation ownership permission. Manager and member starter permissions are seeded during organisation creation. Role changes are written to the organisation audit log.</div><div className="admin-note">This matrix is the configurable permission catalogue. Existing endpoint-specific owner/admin checks remain in force; granular enforcement across every business endpoint is part of the next security hardening pass.</div></section></div>}
    {active==="Organisation settings"&&<div className="admin-columns"><section className="admin-card"><h2>Update setting</h2><p>Settings are scoped to the selected organisation and every change is audited.</p><form className="admin-form" onSubmit={e=>{e.preventDefault();setBusy(true);setError("");setMessage("");request("/v1/tenant/settings/"+setting.key,{method:"PUT",body:JSON.stringify({value:setting.value})}).then(()=>{setMessage("Organisation setting saved.");loadData();}).catch(e=>setError(e.message)).finally(()=>setBusy(false));}}>
      <Field label="Setting"><select value={setting.key} onChange={e=>setSetting({...setting,key:e.target.value,value:data.settings[e.target.value]||""})}>{["timezone","locale","currency","date_format","financial_year_start_month","invoice_prefix","receipt_prefix","default_gst_registration_id","tax_mode","gst_exempt","organisation_display_name"].map(k=><option key={k}>{k}</option>)}</select></Field>
      <Field label="Value"><input value={setting.value} onChange={e=>setSetting({...setting,value:e.target.value})} required/></Field>
      <button className="admin-primary" disabled={busy}>Save setting</button>
    </form></section><section className="admin-card"><h2>Current settings</h2><DataGrid columns={[{key:"key",label:"Setting"},{key:"value",label:"Value"}]} rows={Object.entries(data.settings).map(([key,value])=>({key,value}))}/></section></div>}
    <footer className="admin-footer"><span>{currentOrg?.name || "Selected organisation"} · {currentOrg?.role || "Member"}</span><button onClick={loadData} className="admin-secondary">Refresh data</button><a href="/">Return to NEXA workspace</a></footer>
  </main>;
}
