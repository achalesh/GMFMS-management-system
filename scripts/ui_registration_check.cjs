const { chromium }=require("playwright");
const assert=require("node:assert/strict");
(async()=>{
const browser=await chromium.launch({headless:true,channel:process.env.UI_BROWSER_CHANNEL||"chrome"});
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 const base=(process.env.UI_BASE_URL||"http://127.0.0.1:8001")+"/register/media-facilitator/";
 const errors=[];page.on("pageerror",e=>errors.push(e.message));
 async function layout(label){const d=await page.evaluate(()=>[innerWidth,document.documentElement.scrollWidth]);assert.ok(d[1]<=d[0],label+" overflows: "+d);}
 async function next(number){await page.getByRole("button",{name:"Save & continue →"}).click();await page.waitForURL(base+"step/"+number+"/");await layout("Step "+number);}
 await page.goto(base);await layout("Landing desktop");
 await page.screenshot({path:"artifacts/registration-desktop.png",fullPage:true});
 await page.setViewportSize({width:390,height:844});await layout("Landing mobile");
 await page.screenshot({path:"artifacts/registration-mobile.png",fullPage:true});
 await page.getByRole("button",{name:"Start your application →"}).click();
 const started=Date.now();
 await page.waitForURL(base+"step/1/");
 await page.locator("#id_district").selectOption({label:"Thiruvananthapuram"});
 await page.waitForFunction(()=>document.querySelector("#id_block").options.length===12);
 await page.locator("#id_block").selectOption({index:1});
 await page.waitForFunction(()=>document.querySelector("#id_panchayat").options.length>1);
 await page.locator("#id_panchayat").selectOption({index:1});
 await next(2);
 await page.locator("#id_full_name").fill("Browser QA Applicant");
 await page.locator("#id_mobile").fill("9876543210");
 await page.locator("#id_address").fill("Isolated browser test address");
 await page.locator("#id_pin_code").fill("695001");
 await next(3);
 await page.getByLabel("Photography",{exact:true}).check();
 await page.getByLabel("Malayalam",{exact:true}).check();
 await page.screenshot({path:"artifacts/registration-skills-mobile.png",fullPage:true});
 await next(4);
 await page.getByLabel("Smartphone",{exact:true}).check();
 await next(5);
 await page.locator("#id_photo").setInputFiles("artifacts/registration-test-photo.png");
 await page.locator(".crop-panel").waitFor({state:"visible"});
 await page.locator("#crop-scale").fill("1.5");
 await page.locator("#crop-scale").dispatchEvent("input");
 await page.locator("#id_doc_certificate").setInputFiles("artifacts/registration-test.pdf");
 await layout("Uploads mobile");
 await page.screenshot({path:"artifacts/registration-upload-mobile.png",fullPage:true});
 await next(6);
 await page.getByRole("heading",{name:"Review & consent",exact:true}).waitFor();
 await page.locator(".saved-photo").waitFor();
 await page.screenshot({path:"artifacts/registration-review-mobile.png",fullPage:true});
 await page.locator("#id_accuracy").check();
 await page.locator("#id_processing").check();
 assert.equal(await page.locator("#id_public_mobile").isChecked(),false);
 // Allow the deliberate minimum completion time used by spam protection.
 await page.waitForTimeout(Math.max(0,5500-(Date.now()-started)));
 await page.getByRole("button",{name:"Submit application",exact:true}).click();
 await page.waitForURL(base+"confirmation/");
 const number=await page.locator(".application-number strong").innerText();
 assert.match(number,/^GMF-APP-\d{4}-\d{6,}$/);
 assert.equal(await page.getByText("9876543210",{exact:true}).count(),0);
 await layout("Receipt mobile");
 await page.screenshot({path:"artifacts/registration-confirmation-mobile.png",fullPage:true});
 const stranger=await browser.newPage();
 await stranger.goto(base+"confirmation/");assert.equal(stranger.url(),base);await stranger.close();
 for(const width of [360,768,1440]){
   await page.setViewportSize({width,height:900});
   await page.goto(base);await layout("Landing "+width);
   await page.goto(base+"confirmation/");await layout("Receipt "+width);
 }
 assert.deepEqual(errors,[]);
 console.log("Registration browser checks passed: anonymous six-step application, live dependent dropdowns, photo crop, PDF upload, review and consent, private receipt; desktop/tablet/mobile layouts and no JS errors. QA application: "+number);
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
