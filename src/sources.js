// Read-only Microsoft Graph source adapter. Configuration stays in browser session.
const ROOT="https://graph.microsoft.com/v1.0";
export async function graphJson(token,url){
 if(!url.startsWith(ROOT+"/"))throw Error("Unexpected Graph URL");
 const r=await fetch(url,{headers:{Authorization:"Bearer "+token}});
 if(!r.ok)throw Error("Microsoft Graph returned "+r.status);
 return r.json();
}
export async function listChildren(token,drive,id){
 let url=ROOT+"/drives/"+encodeURIComponent(drive)+"/items/"+encodeURIComponent(id)+"/children?$select=id,name,folder,file,lastModifiedDateTime&$top=200",out=[];
 while(url){const r=await graphJson(token,url);out.push(...(r.value||[]));url=r["@odata.nextLink"]||null}return out;
}
export async function resolveFolder(token,shareUrl){
 const bytes=new TextEncoder().encode(shareUrl);let raw="";for(const b of bytes)raw+=String.fromCharCode(b);
 const key="u!"+btoa(raw).replace(/=/g,"").replace(/\+/g,"-").replace(/\//g,"_");
 const item=await graphJson(token,ROOT+"/shares/"+key+"/driveItem?$select=id,name,folder,parentReference");
 if(!item.folder||!item.parentReference?.driveId)throw Error("Link must identify a shared folder");
 return {drive:item.parentReference.driveId,id:item.id};
}
export async function discoverOrders(token,folder){
 const found=[],queue=[{id:folder.id,path:""}];
 while(queue.length){const parent=queue.shift();for(const x of await listChildren(token,folder.drive,parent.id)){
 const path=parent.path+"/"+x.name;
 if(x.folder)queue.push({id:x.id,path});
 else if(x.file&&/\.xlsx$/i.test(x.name)&&!x.name.startsWith("~$"))found.push({...x,path});
 }}return found.sort((a,b)=>a.path.localeCompare(b.path));
}
export async function downloadItem(token,drive,item){
 // Graph content redirects to a preauthenticated download URL. Do not send the token to that URL.
 const meta=await graphJson(token,ROOT+"/drives/"+encodeURIComponent(drive)+"/items/"+encodeURIComponent(item.id)+"?$select=id,name,@microsoft.graph.downloadUrl");
 const url=meta["@microsoft.graph.downloadUrl"];if(!url||!url.startsWith("https://"))throw Error("No download URL returned");
 const r=await fetch(url);if(!r.ok)throw Error("Workbook download failed: "+r.status);
 return new File([await r.blob()],item.name);
}
