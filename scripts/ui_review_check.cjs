const {chromium}=require("playwright");
const fs=require("node:fs");
const assert=require("node:assert/strict");
(async()=>{
const browser=await chromium.launch({headless:true,channel:process.env.UI_BROWSER_CHANNEL||"chrome"});
try{
 const base=process.env.UI_BASE_URL||"http://127.0.0.1:8001";
 const fixtures=JSON.parse(fs.readFileSync("artifacts/review-fixtures.json","utf8"));
 const credentials=JSON.parse(fs.readFileSync("artifacts/ui-credentials.json","utf8"));
 const context=await browser.newContext({viewport:{width:1440,height:1000}});
 const page=await context.newPage();
 const errors=[];page.on("pageerror",e=>errors.push(e.message));
 async function layout(label){const sizes=await page.evaluate(()=>[innerWidth,document.documentElement.scrollWidth]);assert.ok(sizes[1]<=sizes[0],label+" overflow "+sizes);}
 async function openApp(kind){await page.goto(base+"/applications/"+fixtures[kind].id+"/");}
 async function start(kind){
   await openApp(kind);await page.getByRole("link",{name:"Start review →",exact:true}).click();
   await page.getByRole("button",{name:"Confirm start review",exact:true}).click();
   await page.waitForURL(base+"/applications/"+fixtures[kind].id+"/");
 }
 await page.goto(base+"/accounts/login/");
 await page.getByLabel("Username").fill(credentials.username);await page.getByLabel(/^Password/).fill(credentials.password);
 await page.getByRole("button",{name:"Sign in securely"}).click();await page.waitForURL(base+"/");
 await page.goto(base+"/applications/");await layout("Inbox desktop");await page.screenshot({path:"artifacts/review-inbox-desktop.png",fullPage:true});
 await page.locator("#id_q").fill(fixtures.approve.number);await page.getByRole("button",{name:"Apply filters"}).click();assert.equal(await page.locator("tbody tr").count(),1);
 await start("approve");
 await layout("Review desktop");await page.screenshot({path:"artifacts/review-detail-desktop.png",fullPage:true});
 const download=await page.locator(".document-grid a").last().getAttribute("href");
 const response=await page.request.get(base+download);assert.equal(response.status(),200);assert.match(response.headers()["content-disposition"],/attachment/);
 await page.getByRole("link",{name:"Approve →",exact:true}).click();
 await page.locator("#id_reason").fill("QA: verified documents and reviewed possible duplicate matches.");
 await page.locator("#id_acknowledge_duplicates").check();await page.locator("#id_verification_complete").check();
 await page.getByRole("button",{name:"Confirm approve",exact:true}).click();
 await page.waitForURL(base+"/applications/"+fixtures.approve.id+"/");
 assert.match(await page.locator(".approval-identity strong").innerText(),/^GS-MF-[A-Z]+-\d{4,}$/);
 await page.screenshot({path:"artifacts/review-approved-desktop.png",fullPage:true});
 await start("correct");
 await page.getByRole("link",{name:"Request correction →",exact:true}).click();
 await page.locator("#id_reason").fill("Please update your full name and replace the supporting certificate.");
 await page.getByLabel("Full name",{exact:true}).check();
 await page.getByLabel("Supporting certificate",{exact:true}).check();
 await page.getByRole("button",{name:"Confirm request correction",exact:true}).click();
 const correctionUrl=await page.locator("#correction-url").inputValue();assert.ok(new URL(correctionUrl).hash.length>32);
 const applicantContext=await browser.newContext({viewport:{width:390,height:844}});
 const applicant=await applicantContext.newPage();applicant.on("pageerror",e=>errors.push(e.message));
 await applicant.goto(correctionUrl);
 assert.equal(new URL(applicant.url()).hash,"");
 await applicant.getByRole("button",{name:"Continue securely",exact:true}).click();
 await applicant.getByRole("heading",{name:"Correct your application",exact:true}).waitFor();
 assert.equal(await applicant.locator("#id_mobile").count(),0);
 await applicant.locator("#id_full_name").fill("Browser QA Corrected Applicant");
 await applicant.locator("#id_doc_certificate").setInputFiles("artifacts/registration-test.pdf");
 await applicant.locator("#id_accuracy").check();await applicant.locator("#id_processing").check();
 await applicant.screenshot({path:"artifacts/correction-mobile.png",fullPage:true});
 await applicant.getByRole("button",{name:"Resubmit application",exact:true}).click();
 await applicant.waitForURL(base+"/correct/complete/");
 await applicant.getByRole("heading",{name:"Corrections submitted",exact:true}).waitFor();
 await applicant.goto(correctionUrl);await applicant.getByRole("button",{name:"Continue securely",exact:true}).click();
 await applicant.getByRole("heading",{name:"This correction link is unavailable",exact:true}).waitFor();
 await openApp("correct");await page.getByRole("heading",{name:"Browser QA Corrected Applicant",exact:true}).waitFor();
 await start("reject");await page.getByRole("link",{name:"Reject →",exact:true}).click();
 await page.locator("#id_reason").fill("QA: supporting recommendation could not be verified.");
 await page.getByRole("button",{name:"Confirm reject",exact:true}).click();await page.waitForURL(base+"/applications/"+fixtures.reject.id+"/");
 assert.equal(await page.locator(".page-heading .review-status").innerText(),"Rejected");
 for(const width of [390,360,768]){
  await page.setViewportSize({width,height:844});await page.goto(base+"/applications/");await layout("Inbox "+width);
  await page.screenshot({path:"artifacts/review-inbox-"+width+".png",fullPage:true});
  await openApp("approve");await layout("Detail "+width);
 }
 assert.deepEqual(errors,[]);
 console.log("Phase 4 browser checks passed: scoped inbox/search, private download, review/approval and official ID, correction link exchange and document resubmission, single-use link denial, rejection; desktop/tablet/mobile layouts; no JS errors.");
 await applicantContext.close();await context.close();
}finally{await browser.close();}
})().catch(error=>{console.error(error);process.exit(1)});
