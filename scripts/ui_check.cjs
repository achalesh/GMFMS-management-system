// Run with NODE_PATH pointing to an installation of playwright; see INSTALLATION.md.
const { chromium } = require("playwright");
const fs = require("node:fs");
const path = require("node:path");
(async () => {
  const browser = await chromium.launch({headless: true, channel: process.env.UI_BROWSER_CHANNEL || "chrome"});
  const context = await browser.newContext({viewport: {width: 1440, height: 1050}});
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  const base = process.env.UI_BASE_URL || "http://127.0.0.1:8001";
  const credentials = JSON.parse(fs.readFileSync(path.join(__dirname, "../artifacts/ui-credentials.json"), "utf8"));
  async function noOverflow(label) {
    const dimensions = await page.evaluate(() => ({viewport:innerWidth, page:document.documentElement.scrollWidth}));
    if(dimensions.page > dimensions.viewport) throw new Error(label + " has horizontal overflow: " + JSON.stringify(dimensions));
  }
  await page.goto(base + "/accounts/login/");
  await page.screenshot({path:"artifacts/login-desktop.png",fullPage:true});
  await page.getByLabel("Username").fill(credentials.username);
  await page.getByLabel(/^Password/).fill(credentials.password);
  await page.getByRole("button", {name:"Sign in securely"}).click();
  await page.waitForURL(base + "/");
  await page.getByRole("heading", {name:"Workspace overview"}).waitFor();
  await noOverflow("desktop dashboard");
  await page.screenshot({path:"artifacts/dashboard-desktop.png",fullPage:true});
  await page.locator('.nav-stack a[href="/settings/organization/"]').click();
  await page.getByLabel(/^Short name/).fill("Gramaswaraj");
  await page.getByRole("button", {name:"Save changes"}).click();
  await page.getByRole("status").filter({hasText:"Settings saved"}).waitFor();
  await page.screenshot({path:"artifacts/settings-desktop.png",fullPage:true});
  for(const width of [390, 360, 768]) {
    await page.setViewportSize({width,height:844});
    await page.goto(base + "/");
    await noOverflow("dashboard " + width);
    if(width < 768) {
      const toggle = page.getByRole("button",{name:"Toggle navigation"});
      await toggle.click();
      await page.locator('.nav-stack a[href="/profile/"]').click();
      await page.getByRole("heading",{name:"My access",exact:true}).waitFor();
      await noOverflow("profile " + width);
      await page.goto(base + "/settings/organization/");
      await noOverflow("settings " + width);
      await page.goto(base + "/");
    }
    await page.screenshot({path:"artifacts/dashboard-" + width + ".png",fullPage:true});
  }
  await page.setViewportSize({width:390,height:844});
  await page.getByRole("button",{name:"Sign out"}).click();
  await page.waitForURL(base + "/accounts/login/");
  await noOverflow("mobile login");
  await page.screenshot({path:"artifacts/login-mobile.png",fullPage:true});
  await page.getByRole("link",{name:"Forgot your password?"}).click();
  await page.getByRole("heading",{name:"Reset your password"}).waitFor();
  await noOverflow("mobile reset");
  if(errors.length) throw new Error("Browser errors: " + errors.join("; "));
  console.log("UI checks passed: login, settings save, logout, reset, desktop/tablet/mobile overflow, mobile navigation; no JS errors.");
  await browser.close();
})().catch(error => {console.error(error);process.exit(1)});
