const { chromium } = require("playwright");
const fs = require("node:fs");
const assert = require("node:assert/strict");
(async () => {
 const browser = await chromium.launch({headless:true,channel:process.env.UI_BROWSER_CHANNEL || "chrome"});
 try {
 const page = await browser.newPage({viewport:{width:1440,height:1000}});
 const errors = [];
 page.on("pageerror", e => errors.push(e.message));
 const base = process.env.UI_BASE_URL || "http://127.0.0.1:8001";
 const credentials = JSON.parse(fs.readFileSync("artifacts/ui-credentials.json","utf8"));
 await page.goto(base + "/accounts/login/");
 await page.getByLabel("Username").fill(credentials.username);
 await page.getByLabel(/^Password/).fill(credentials.password);
 await page.getByRole("button",{name:"Sign in securely"}).click();
 await page.waitForURL(base + "/");
 await page.goto(base + "/locations/");
 await page.getByRole("heading",{name:"Kerala location master",exact:true}).waitFor();
 assert.equal(await page.locator(".district-card").count(),14);
 assert.equal(await page.locator(".location-banner-stat strong").innerText(),"941");
 await page.screenshot({path:"artifacts/locations-desktop.png",fullPage:true});
 await page.locator(".district-card").filter({hasText:"Thiruvananthapuram"}).click();
 assert.equal(await page.locator("tbody tr").count(),11);
 await page.goto(base + "/locations/panchayats/");
 await page.getByLabel("District",{exact:true}).selectOption({label:"Thiruvananthapuram"});
 await page.waitForFunction(() => document.querySelector("#id_block").options.length === 12);
 await page.getByLabel("Block",{exact:true}).selectOption({index:1});
 const selectedBlock = await page.getByLabel("Block",{exact:true}).inputValue();
 await page.getByRole("button",{name:"Apply filters"}).click();
 const data = await (await page.request.get(base + "/api/v1/panchayats/?block=" + selectedBlock)).json();
 assert.equal(await page.locator("tbody tr").count(),data.count);
 await page.locator("tbody tr a").first().click();
 await page.getByRole("link",{name:/Edit/}).click();
 await page.getByLabel(/^Reason/).fill("Browser validation in isolated QA database");
 await page.getByRole("button",{name:"Save location"}).click();
 await page.getByRole("status").filter({hasText:"Location updated"}).waitFor();
 await page.goto(base + "/locations/import/");
 await page.getByLabel("CSV or XLSX file").setInputFiles("data/kerala/locations.csv");
 await page.getByLabel(/^Source/).fill("Bundled official snapshot — isolated browser dry run");
 assert.equal(await page.getByLabel("Validate only (dry run)",{exact:true}).isChecked(),true);
 await page.getByRole("button",{name:"Process file"}).click();
 await page.getByRole("status").filter({hasText:"Validation passed; no changes saved."}).waitFor();
 await page.screenshot({path:"artifacts/location-import-desktop.png",fullPage:true});
 for(const width of [1440,768,390,360]) {
   await page.setViewportSize({width,height:844});
   for(const route of ["/locations/","/locations/panchayats/","/locations/import/"]) {
     await page.goto(base + route);
     const dims = await page.evaluate(() => [innerWidth,document.documentElement.scrollWidth]);
     assert.ok(dims[1] <= dims[0],route+" overflows at "+width+": "+dims);
   }
   await page.goto(base + "/locations/");
   await page.screenshot({path:"artifacts/locations-"+width+".png",fullPage:true});
 }
 assert.deepEqual(errors,[]);
 console.log("Phase 2 browser checks passed: full master, district drill-down, dynamic block filter, public Panchayat API, audited edit, dry-run import; 1440/768/390/360 layouts; no JavaScript errors.");
 } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exit(1)});
