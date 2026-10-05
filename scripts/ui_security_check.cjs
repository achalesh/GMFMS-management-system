const {chromium}=require('playwright');const assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({headless:true,channel:'chrome'});try{
const page=await browser.newPage();
await page.addInitScript(()=>{window.cspViolations=[];document.addEventListener('securitypolicyviolation',e=>window.cspViolations.push(e.effectiveDirective));});
const response=await page.goto('http://127.0.0.1:8001/accounts/login/');
assert.equal(response.headers()['referrer-policy'],'same-origin');assert.match(response.headers()['content-security-policy'],/script-src 'self'/);
await page.evaluate(()=>{const s=document.createElement('script');s.textContent='window.untrustedInlineRan=true';document.body.appendChild(s);});
assert.equal(await page.evaluate(()=>!!window.untrustedInlineRan),false);
await page.waitForFunction(()=>window.cspViolations.length>0);
await page.goto('http://127.0.0.1:8001/register/media-facilitator/');
assert.deepEqual(await page.evaluate(()=>window.cspViolations),[]);
console.log('Browser security checks passed: response headers, inline script rejection, registration page compatibility.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1)});
