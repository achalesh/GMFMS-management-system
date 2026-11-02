document.querySelectorAll('[data-training-form]').forEach(button=>{
 button.addEventListener('click',()=>{const form=document.getElementById(button.dataset.trainingForm);if(!form)return;document.querySelectorAll('input[type="checkbox"]').forEach(input=>{if(input.form===form&&!input.disabled){input.checked=button.dataset.trainingSelect==='all';input.dispatchEvent(new Event('change',{bubbles:true}));}});});
});
