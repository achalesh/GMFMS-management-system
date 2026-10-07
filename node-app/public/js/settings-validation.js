const website=document.querySelector('#website');
if(website){
 const validate=()=>{
  const value=website.value.trim();let valid=true;
  if(value)try{const url=new URL(value);valid=['http:','https:'].includes(url.protocol)&&!url.username&&!url.password;}catch{valid=false;}
  website.setCustomValidity(valid?'':'Enter an HTTP or HTTPS website without embedded credentials.');
  website.classList.toggle('is-invalid',!valid);
  website.setAttribute('aria-invalid',String(!valid));
 };
 website.addEventListener('input',validate);
 website.addEventListener('blur',validate);
 website.addEventListener('invalid',validate);
 website.form.addEventListener('submit',validate);
}
