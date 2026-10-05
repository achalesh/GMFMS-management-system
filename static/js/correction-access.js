(() => {
"use strict";
const input=document.querySelector("#correction-token");
if(!input)return;
const token=location.hash.slice(1);
history.replaceState(null,"",location.pathname+location.search);
if(/^[A-Za-z0-9_-]{32,100}$/.test(token)){
 input.value=token;
}
})();