import {resolveFolder,discoverOrders,listChildren,downloadItem} from "./sources.js";
const $=id=>document.getElementById(id);
let auth=null,account=null,orders=[],trades=null;
function status(s){$("status").textContent=s}
async function token(){
 if(!auth||!account)throw Error("Connect to Microsoft 365 first");
 const request={account,scopes:["Files.Read","Sites.Read.All"]};
 try{return (await auth.acquireTokenSilent(request)).accessToken}catch{return (await auth.acquireTokenPopup(request)).accessToken}
}
function showOrders(files,source){orders=files;$("orderStatus").textContent=source+": "+files.length+" workbook(s) loaded; validation pending.";$("orderList").replaceChildren(...files.map(f=>{const li=document.createElement("li");li.textContent=f.name;return li}))}
function showTrades(file,source){trades=file;$("tradeStatus").textContent=source+": "+file.name+"; validation pending."}
async function run(button,fn){button.disabled=true;try{await fn()}catch(e){status("Error: "+e.message)}finally{button.disabled=false}}
$("connect").onclick=()=>run($("connect"),async()=>{
 const client=$("client").value.trim(),tenant=$("tenant").value.trim();
 if(!/^[a-f0-9-]{36}$/i.test(client)||!/^[a-f0-9-]{36}$/i.test(tenant))throw Error("Enter the registered client and tenant IDs");
 auth=new msal.PublicClientApplication({auth:{clientId:client,authority:"https://login.microsoftonline.com/"+tenant,redirectUri:location.origin+location.pathname},cache:{cacheLocation:"sessionStorage"}});
 await auth.initialize();const r=await auth.loginPopup({scopes:["Files.Read","Sites.Read.All"],prompt:"select_account"});
 if(r.account?.tenantId!==tenant)throw Error("Unexpected tenant");account=r.account;status("Microsoft 365 connected.");
});
$("autoOrders").onclick=()=>run($("autoOrders"),async()=>{
 status("Discovering Excel workbooks…");const t=await token(),folder=await resolveFolder(t,$("ordersLink").value.trim()),items=await discoverOrders(t,folder);
 if(!items.length)throw Error("No Excel workbooks found");
 // Display candidates only: do not assume every workbook is an order.
 $("orderList").replaceChildren();const selected=[];
 for(const item of items){const li=document.createElement("li"),label=document.createElement("label"),check=document.createElement("input");check.type="checkbox";label.append(check,document.createTextNode(item.path));li.append(label);$("orderList").append(li);selected.push({item,check})}
 const b=document.createElement("button");b.textContent="Load selected order workbooks";$("orderList").append(b);
 b.onclick=()=>run(b,async()=>{const chosen=selected.filter(x=>x.check.checked);if(!chosen.length)throw Error("Select at least one workbook");const files=[];for(const x of chosen)files.push(await downloadItem(await token(),folder.drive,x.item));showOrders(files,"Automatic");status("Selected workbooks loaded.")});
 $("orderStatus").textContent=items.length+" candidate workbooks found. Select original order files.";status("Discovery complete; filename conventions still require validation.");
});
$("autoTrades").onclick=()=>run($("autoTrades"),async()=>{
 const t=await token(),folder=await resolveFolder(t,$("tradesLink").value.trim()),items=await listChildren(t,folder.drive,folder.id);
 const matches=items.filter(x=>x.file&&x.name.toLowerCase()==="combined_trades_history.xlsx");
 if(matches.length!==1)throw Error("Expected exactly one COMBINED_Trades_History.xlsx");
 showTrades(await downloadItem(t,folder.drive,matches[0]),"Automatic");status("Bank trades workbook loaded.");
});
$("manualOrders").onchange=()=>{const files=[...$("manualOrders").files];if(files.length)showOrders(files,"Manual")};
$("manualTrades").onchange=()=>{const f=$("manualTrades").files[0];if(f)showTrades(f,"Manual")};
