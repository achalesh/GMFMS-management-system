const {chromium}=require("playwright");
const fs=require("node:fs"),assert=require("node:assert/strict");
(async()=>{const browser=await chromium.launch({headless:true,channel:"chrome"});try{
const base="http://127.0.0.1:8001";
const credentials=JSON.parse(fs.readFileSync("artifacts/ui-credentials.json","utf8"));
const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on("pageerror",e=>errors.push(e.message));
await page.goto(base+"/accounts/login/");await page.getByLabel("Username").fill(credentials.username);await page.getByLabel(/^Password/).fill(credentials.password);await page.getByRole("button",{name:"Sign in securely"}).click();await page.waitForURL(base+"/");
assert.ok(await page.getByRole("heading",{name:/Network coverage/}).count());
await page.screenshot({path:"artifacts/phase8-dashboard-desktop.png",fullPage:true});
await page.locator('a[href^="/dashboard/districts/"]').first().click();assert.equal(await page.locator('a[href^="/dashboard/blocks/"]').count()>0,true);
await page.locator('a[href^="/dashboard/blocks/"]').first().click();assert.ok(await page.getByRole('heading',{name:'Facilitators in this block'}).count());
for(const width of [390,360,768]){await page.setViewportSize({width,height:900});await page.goto(base+'/');assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:'artifacts/phase8-dashboard-'+width+'.png',fullPage:true});}
for(const kind of ['coverage','vacancies','facilitators','applications','expiring','skills','equipment','progress','history']){const response=await page.goto(base+'/reports/?report='+kind);assert.equal(response.status(),200);}
await page.goto(base+'/reports/?report=facilitators');
for(const fmt of ['csv','xlsx','pdf']){await page.locator('#id_format').selectOption(fmt);await page.locator('#id_reason').fill('Synthetic QA report validation');const pending=page.waitForEvent('download');await page.getByRole('button',{name:'Download report',exact:true}).click();await (await pending).saveAs('artifacts/phase8-facilitators.'+fmt);}
for(const width of [390,360,768,1440]){await page.setViewportSize({width,height:900});await page.goto(base+'/reports/?report=facilitators');assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:'artifacts/phase8-reports-'+width+'.png',fullPage:true});}
assert.deepEqual(errors,[]);console.log('Phase 8 browser checks passed: dashboard drilldowns, 9 report types, 3 downloads, responsive layouts, no JavaScript errors.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1)});
