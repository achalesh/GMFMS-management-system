(() => {
"use strict";
const form = document.querySelector("[data-registration-step]");
if (!form) return;
if (form.dataset.registrationStep === "1") {
 const district = document.querySelector("#id_district"), block = document.querySelector("#id_block"), panchayat = document.querySelector("#id_panchayat");
 const feedback = document.querySelector(".dropdown-feedback");
 let generation = 0;
 const clear = (select,label) => { select.replaceChildren(new Option(label,"")); };
 async function load(url,target,token) {
  target.disabled = true;
  try {
   const items = [];
   while(url) {
    const response = await fetch(url,{headers:{"Accept":"application/json"}});
    if(!response.ok) throw new Error("Unable to load locations. Please try again shortly.");
    const data = await response.json();
    items.push(...data.results);
    url = data.next;
   }
   if(token !== generation) return;
   for(const item of items) target.add(new Option(item.name_en,item.id));
  } catch(error) { if(token === generation) feedback.textContent = error.message; }
  finally { if(token === generation) target.disabled = false; }
 }
 district.addEventListener("change",() => {
  const token = ++generation;
  feedback.textContent = ""; clear(block,"Select a block"); clear(panchayat,"Select a Panchayat");
  block.disabled = false; panchayat.disabled = false;
  if(district.value) load("/api/v1/blocks/?district="+encodeURIComponent(district.value),block,token);
 });
 block.addEventListener("change",() => {
  const token = ++generation;
  feedback.textContent = ""; clear(panchayat,"Select a Panchayat"); panchayat.disabled = false;
  if(block.value) load("/api/v1/panchayats/?block="+encodeURIComponent(block.value),panchayat,token);
 });
}
if(form.dataset.registrationStep === "5") {
 const file = document.querySelector("#id_photo"), panel=document.querySelector(".crop-panel"), canvas=document.querySelector("#crop-preview");
 const x=document.querySelector("#crop-horizontal"),y=document.querySelector("#crop-vertical"),zoom=document.querySelector("#crop-scale");
 const status=document.querySelector("#crop-status");
 let portrait=null, objectUrl=null, version=0;
 function draw() {
  if(!portrait) return;
  const width=Math.min(portrait.naturalWidth,portrait.naturalHeight*.75)/Number(zoom.value),height=width/.75;
  const left=(portrait.naturalWidth-width)*Number(x.value)/100,top=(portrait.naturalHeight-height)*Number(y.value)/100;
  canvas.getContext("2d").drawImage(portrait,left,top,width,height,0,0,300,400);
  document.querySelector("#id_crop_x").value=x.value;
  document.querySelector("#id_crop_y").value=y.value;
  document.querySelector("#id_crop_zoom").value=zoom.value;
 }
 file.addEventListener("change",()=>{
  const token=++version;
  panel.hidden=true; portrait=null; status.textContent="";
  if(objectUrl) URL.revokeObjectURL(objectUrl);
  if(!file.files.length) return;
  if(file.files[0].size > 20*1024*1024) { status.textContent="Choose a smaller image."; return; }
  objectUrl=URL.createObjectURL(file.files[0]);
  const image=new Image();
  image.onload=()=>{if(token !== version)return;portrait=image;x.value=y.value=50;zoom.value=1;panel.hidden=false;draw();};
  image.onerror=()=>{if(token===version)status.textContent="This file could not be previewed. Choose a JPG or PNG photograph.";};
  image.src=objectUrl;
 });
 for(const control of [x,y,zoom]) control.addEventListener("input",draw);
}
// Avoid repeat clicks while retaining server-side idempotency as the authority.
form.addEventListener("submit",()=>{const button=form.querySelector("button[type=submit]");if(button){button.disabled=true;button.textContent="Saving…";}});
})();
