const district=document.getElementById('district'),block=document.getElementById('block'),panchayat=document.getElementById('panchayat');
const blocks=[...block.options].map(o=>o.cloneNode(true)),panchayats=[...panchayat.options].map(o=>o.cloneNode(true));
function updatePanchayats(){const value=panchayat.value;panchayat.replaceChildren(...panchayats.filter(o=>!o.value||o.dataset.block===block.value).map(o=>o.cloneNode(true)));panchayat.value=[...panchayat.options].some(o=>o.value===value)?value:'';}
function updateBlocks(){const value=block.value;block.replaceChildren(...blocks.filter(o=>!o.value||o.dataset.district===district.value).map(o=>o.cloneNode(true)));block.value=[...block.options].some(o=>o.value===value)?value:'';updatePanchayats();}
district.addEventListener('change',updateBlocks);block.addEventListener('change',updatePanchayats);updateBlocks();
