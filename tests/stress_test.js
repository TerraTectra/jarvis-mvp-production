const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const { logWithTimestamp } = require('../scripts/kwork_node_bridge');

// Test configuration
const CONFIG = {
  BASE_URL: 'https://kwork.ru',
  TEST_DURATION: 30 * 60 * 1000, // 30 minutes
  REQUEST_DELAY: { min: 2000, max: 5000 }, // Random delay between requests in ms
  RATE_LIMIT: { requests: 30, perMinutes: 10 }, // Rate limiting
  TEST_SCENARIOS: [
    'network_failure',
    'timeout',
    'captcha',
    'success'
  ]
};

// Test metrics
const metrics = {
  startTime: null,
  endTime: null,
  totalRequests: 0,
  successfulRequests: 0,
  failedRequests: 0,
  retries: 0,
  sessionStarts: 0,
  sessionEnds: 0,
  errors: [],
  requests: [],
  rateLimitsHit: 0
};

// Rate limiting state
const rateLimitState = {
  requestCount: 0,
  lastReset: Date.now()
};

/**
 * Check and enforce rate limiting
 */
function checkRateLimit() {
  const now = Date.now();
  const minutesSinceReset = (now - rateLimitState.lastReset) / (60 * 1000);
  
  if (minutesSinceReset >= CONFIG.RATE_LIMIT.perMinutes / 60) {
    rateLimitState.requestCount = 0;
    rateLimitState.lastReset = now;
  }
  
  if (rateLimitState.requestCount >= CONFIG.RATE_LIMIT.requests) {
    const waitTime = (CONFIG.RATE_LIMIT.perMinutes * 60 * 1000) - (now - rateLimitState.lastReset);
    logWithTimestamp(`⚠️ Rate limit reached. Waiting ${Math.ceil(waitTime/1000)} seconds...`);
    metrics.rateLimitsHit++;
    return waitTime;
  }
  
  rateLimitState.requestCount++;
  return 0;
}

/**
 * Simulate network failure
 */
async function simulateNetworkFailure(page) {
  try {
    logWithTimestamp('🚧 Simulating network failure...');
    await page.setOfflineMode(true);
    await new Promise(resolve => setTimeout(resolve, 5000));
    await page.setOfflineMode(false);
    logWithTimestamp('✅ Network restored');
  } catch (error) {
    logWithTimestamp('❌ Network failure simulation error:', error.message);
  }
}

/**
 * Simulate timeout
 */
async function simulateTimeout(page) {
  logWithTimestamp('⏱️ Simulating timeout...');
  await page.route('**/*', route => {
    // Delay response to simulate timeout
    setTimeout(() => route.continue(), 30000); // 30s delay
  });
  
  await new Promise(resolve => setTimeout(resolve, 10000));
  
  // Remove the route handler
  await page.unroute('**/*');
  logWithTimestamp('✅ Timeout simulation complete');
}

/**
 * Simulate captcha
 */
async function simulateCaptcha(page) {
  logWithTimestamp('🛡️ Simulating captcha...');
  await page.evaluate(() => {
    // Create a fake captcha element
    const captcha = document.createElement('div');
    captcha.id = 'captcha';
    captcha.innerHTML = 'Please complete the CAPTCHA to continue';
    captcha.style.position = 'fixed';
    captcha.style.top = '20px';
    captcha.style.left = '50%';
    captcha.style.transform = 'translateX(-50%)';
    captcha.style.padding = '20px';
    captcha.style.background = 'white';
    captcha.style.border = '2px solid red';
    captcha.style.zIndex = '9999';
    document.body.appendChild(captcha);
  });
  
  await new Promise(resolve => setTimeout(resolve, 5000));
  
  // Remove the captcha simulation
  await page.evaluate(() => {
    const captcha = document.getElementById('captcha');
    if (captcha) captcha.remove();
  });
  
  logWithTimestamp('✅ Captcha simulation complete');
}

/**
 * Run a test scenario
 */
async function runTest(scenario, page) {
  const testStart = Date.now();
  let success = false;
  let error = null;
  
  try {
    metrics.totalRequests++;
    
    // Enforce rate limiting
    const waitTime = checkRateLimit();
    if (waitTime > 0) {
      await new Promise(resolve => setTimeout(resolve, waitTime));
    }
    
    logWithTimestamp(`🚀 Starting scenario: ${scenario}`);
    
    // Run the scenario
    switch (scenario) {
      case 'network_failure':
        await simulateNetworkFailure(page);
        break;
      case 'timeout':
        await simulateTimeout(page);
        break;
      case 'captcha':
        await simulateCaptcha(page);
        break;
      case 'success':
        // Normal operation
        await page.goto(CONFIG.BASE_URL, { waitUntil: 'domcontentloaded' });
        break;
    }
    
    success = true;
    metrics.successfulRequests++;
    logWithTimestamp(`✅ Scenario ${scenario} completed successfully`);
  } catch (err) {
    success = false;
    metrics.failedRequests++;
    error = err;
    metrics.errors.push({
      scenario,
      time: new Date().toISOString(),
      error: err.message,
      stack: err.stack
    });
    logWithTimestamp(`❌ Scenario ${scenario} failed: ${err.message}`);
    
    // Take screenshot on error
    try {
      const screenshotPath = path.join(__dirname, 'screenshots', `error-${Date.now()}.png`);
      await page.screenshot({ path: screenshotPath });
      logWithTimestamp(`📸 Screenshot saved to ${screenshotPath}`);
    } catch (screenshotErr) {
      logWithTimestamp('Failed to take screenshot:', screenshotErr.message);
    }
  } finally {
    const duration = Date.now() - testStart;
    metrics.requests.push({
      scenario,
      success,
      duration,
      timestamp: new Date().toISOString(),
      error: error ? error.message : null
    });
    
    // Random delay between tests
    const delay = Math.floor(Math.random() * (CONFIG.REQUEST_DELAY.max - CONFIG.REQUEST_DELAY.min + 1)) + CONFIG.REQUEST_DELAY.min;
    await new Promise(resolve => setTimeout(resolve, delay));
  }
}

/**
 * Save test results
 */
function saveResults() {
  const resultsDir = path.join(__dirname, 'results');
  if (!fs.existsSync(resultsDir)) {
    fs.mkdirSync(resultsDir, { recursive: true });
  }
  
  const resultFile = path.join(resultsDir, `stress-test-${new Date().toISOString().replace(/[:.]/g, '-')}.json`);
  
  const results = {
    config: CONFIG,
    metrics: {
      ...metrics,
      testDuration: metrics.endTime - metrics.startTime,
      successRate: (metrics.successfulRequests / metrics.totalRequests) * 100
    },
    requests: metrics.requests,
    errors: metrics.errors
  };
  
  fs.writeFileSync(resultFile, JSON.stringify(results, null, 2));
  logWithTimestamp(`📊 Test results saved to ${resultFile}`);
  
  // Print summary
  console.log('\n=== Test Summary ===');
  console.log(`Duration: ${(results.metrics.testDuration / 1000 / 60).toFixed(2)} minutes`);
  console.log(`Total Requests: ${results.metrics.totalRequests}`);
  console.log(`Successful: ${results.metrics.successfulRequests}`);
  console.log(`Failed: ${results.metrics.failedRequests}`);
  console.log(`Success Rate: ${results.metrics.successRate.toFixed(2)}%`);
  console.log(`Rate Limits Hit: ${results.metrics.rateLimitsHit}`);
  console.log(`Sessions Started: ${results.metrics.sessionStarts}`);
  console.log(`Sessions Ended: ${results.metrics.sessionEnds}`);
  console.log(`Total Retries: ${results.metrics.retries}`);
}

/**
 * Main test runner
 */
async function runStressTest() {
  logWithTimestamp('🚀 Starting Kwork Bridge Stress Test');
  metrics.startTime = Date.now();
  
  const browser = await chromium.launch({
    headless: true,
    timeout: 60000
  });
  
  metrics.sessionStarts++;
  
  try {
    const context = await browser.newContext({
      viewport: { width: 1280, height: 1024 },
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
      ignoreHTTPSErrors: true
    });
    
    const page = await context.newPage();
    
    // Run tests until duration is reached
    const testEndTime = Date.now() + CONFIG.TEST_DURATION;
    let testCount = 0;
    
    while (Date.now() < testEndTime) {
      const scenario = CONFIG.TEST_SCENARIOS[testCount % CONFIG.TEST_SCENARIOS.length];
      await runTest(scenario, page);
      testCount++;
      
      // Save progress every 10 tests
      if (testCount % 10 === 0) {
        metrics.endTime = Date.now();
        saveResults();
      }
    }
    
  } catch (error) {
    logWithTimestamp('❌ Test runner error:', error);
  } finally {
    metrics.endTime = Date.now();
    metrics.sessionEnds++;
    await browser.close();
    saveResults();
    logWithTimestamp('🏁 Stress test completed');
  }
}

// Create screenshots directory if it doesn't exist
const screenshotsDir = path.join(__dirname, 'screenshots');
if (!fs.existsSync(screenshotsDir)) {
  fs.mkdirSync(screenshotsDir, { recursive: true });
}

// Run the test
runStressTest().catch(console.error);
