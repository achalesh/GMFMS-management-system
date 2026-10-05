const {chromium}=require("playwright");
const fs=require("node:fs");const assert=require("node:assert/strict");
(async()=>{const browser=await chromium.launch({headless:true,channel:process.env.UI_BROWSER_CHANNEL||"chrome"});
try {
const base=process.env.UI_BASE_URL||"http://127.0.0.1:8001";
const fixture=JSON.parse(fs.readFileSync("artifacts/registry-fixtures.json","utf8"));
const credentials=JSON.parse(fs.readFileSync("artifacts/ui-credentials.json","utf8"));
const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on("pageerror",e=>errors.push(e.message));
async function layout(name){const sizes=await page.evaluate(()=>[innerWidth,document.documentElement.scrollWidth]);assert.ok(sizes[1]<=sizes[0],name+" overflow "+sizes);}
async function detail(){await page.goto(base+"/facilitators/"+fixture.id+"/");await page.getByRole("heading",{name:"Registry QA Facilitator",exact:true}).waitFor();}
async function action(key,fill){await page.goto(base+"/facilitators/"+fixture.id+"/actions/"+key+"/");await page.locator("#id_reason").fill("Synthetic browser QA: authorized and verified change.");if(fill)await fill();await page.getByRole("button",{name:/^Confirm /}).click();await page.waitForURL(base+"/facilitators/"+fixture.id+"/");}
await page.goto(base+"/accounts/login/");await page.getByLabel("Username").fill(credentials.username);await page.getByLabel(/^Password/).fill(credentials.password);await page.getByRole("button",{name:"Sign in securely"}).click();await page.waitForURL(base+"/");
await page.goto(base+"/facilitators/");await page.locator("summary").click();await page.locator("#id_q").fill(fixture.number);await page.getByRole("button",{name:"Apply filters"}).click();assert.equal(await page.locator("tbody tr").count(),1);await layout("registry desktop");await page.screenshot({path:"artifacts/registry-desktop.png",fullPage:true});
await detail();assert.equal(await page.locator(".registry-portrait").evaluate(img=>img.complete&&img.naturalWidth>0),true);await page.screenshot({path:"artifacts/registry-detail-desktop.png",fullPage:true});
await action("suspend");assert.equal(await page.locator(".page-heading .status-pill").innerText(),"SUSPENDED");
await action("reactivate");assert.equal(await page.locator(".page-heading .status-pill").innerText(),"ACTIVE");
await action("renew",async()=>{const date=new Date();date.setUTCFullYear(date.getUTCFullYear()+2);await page.locator("#id_valid_until").fill(date.toISOString().slice(0,10));});
await action("transfer",async()=>await page.locator("#id_panchayat").selectOption(String(fixture.destination)));
assert.equal(await page.locator(".table tbody tr").count(),2);
await page.goto(base+"/facilitators/panchayats/"+fixture.source+"/");assert.match(await page.locator(".page-heading .tag").innerText(),/vacant/);
await detail();await action("replace",async()=>{await page.locator("#id_replacement").selectOption(fixture.incoming+":"+fixture.incoming_revision);await page.locator("#id_verification_complete").check();await page.locator("#id_acknowledge_duplicates").check();});assert.equal(await page.locator(".page-heading .status-pill").innerText(),"REPLACED");
await page.goto(base+"/facilitators/panchayats/"+fixture.destination+"/");assert.match(await page.locator(".page-heading .tag").innerText(),/covered/);assert.match(await page.locator("main").innerText(),/Registry QA Successor/);await page.screenshot({path:"artifacts/registry-panchayat-desktop.png",fullPage:true});
for(const width of [390,360,768]){await page.setViewportSize({width,height:900});for(const path of ["/facilitators/","/facilitators/coverage/","/facilitators/"+fixture.id+"/","/facilitators/panchayats/"+fixture.destination+"/"]){await page.goto(base+path);await layout(path+width);}await page.screenshot({path:"artifacts/registry-mobile-"+width+".png",fullPage:true});}
assert.deepEqual(errors,[]);console.log("Registry browser checks passed: search, portrait, suspension/reactivation, renewal, transfer, atomic replacement, vacancy and institutional history; desktop/tablet/mobile; no JS errors.");
}finally{await browser.close();}})().catch(error=>{console.error(error);process.exit(1)});
