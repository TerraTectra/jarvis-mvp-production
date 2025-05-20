const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const monitor = require('../scripts/monitor');
const { logWithTimestamp } = require('../scripts/kwork_node_bridge');

// Test configuration
const CONFIG = {
  MAX_RUNS: 3,               // Number of full scenario cycles to run
  SCENARIO_DELAY: 2000,      // Fixed delay between scenarios in ms
  RATE_LIMIT: {
    requests: 30,              // Max requests
    perMinutes: 10,          // Per 10 minutes
    cooldown: 60000          // 1 minute cooldown when limit hit
  },
  SCENARIOS: [
    'network_failure',
    'timeout',
    'captcha',
    'success'
  ]
};

// Test state
const state = {
  browser: null,
  page: null,
  isRunning: false,
  rateLimit: {
    count: 0,
    resetTime: Date.now()
  },
  stats: {
    scenariosRun: 0,
    scenariosPassed: 0,
    scenariosFailed: 0,
    errors: []
  }
};

/**
 * Check and enforce rate limiting
 */
function checkRateLimit() {
  const now = Date.now();
  
  // Reset counter if time window has passed
  if (now > state.rateLimit.resetTime) {
    state.rateLimit.count = 0;
    state.rateLimit.resetTime = now + (CONFIG.RATE_LIMIT.perMinutes * 60 * 1000);
  }
  
  // Check if rate limit exceeded
  if (state.rateLimit.count >= CONFIG.RATE_LIMIT.requests) {
    const waitTime = state.rateLimit.resetTime - now;
    monitor.trackRateLimit();
    return waitTime;
  }
  
  state.rateLimit.count++;
  return 0;
}

/**
 * Simulate network failure
 */
async function simulateNetworkFailure() {
  const startTime = Date.now();
  let success = false;
  let client = null;
  
  try {
    monitor.log('🚧 Simulating network failure...');
    
    // Get CDP session for the page
    client = await state.page.context().newCDPSession(state.page);
    
    // Enable network conditions emulation
    await client.send('Network.enable');
    
    // Set offline mode
    await client.send('Network.emulateNetworkConditions', {
      offline: true,
      downloadThroughput: 0,
      uploadThroughput: 0,
      latency: 0,
    });
    
    // Wait for 5 seconds in offline mode
    await new Promise(resolve => setTimeout(resolve, 5000));
    
    // Restore online mode
    await client.send('Network.emulateNetworkConditions', {
      offline: false,
      downloadThroughput: -1,
      uploadThroughput: -1,
      latency: 0,
    });
    
    success = true;
    monitor.log('✅ Network restored');
  } catch (error) {
    monitor.log(`❌ Network failure simulation error: ${error.message}`);
    throw error;
  } finally {
    // Clean up CDP session
    if (client) {
      await client.detach().catch(e => console.error('Error detaching CDP session:', e));
    }
    
    monitor.trackRequest('network_failure', success, Date.now() - startTime, {
      error: success ? null : 'Network failure simulation failed'
    });
  }
}

/**
 * Simulate timeout
 */
async function simulateTimeout() {
  const startTime = Date.now();
  let success = false;
  
  try {
    monitor.log('⏱️ Simulating timeout...');
    await state.page.route('**/*', route => {
      // Delay response to simulate timeout
      setTimeout(() => route.continue(), 30000); // 30s delay
    });
    
    await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        state.page.unroute('**/*');
        resolve();
      }, 10000);
    });
    
    success = true;
    monitor.log('✅ Timeout simulation complete');
  } catch (error) {
    monitor.log(`❌ Timeout simulation error: ${error.message}`);
    throw error;
  } finally {
    await state.page.unroute('**/*');
    monitor.trackRequest('timeout', success, Date.now() - startTime, {
      error: success ? null : 'Timeout simulation failed'
    });
  }
}

/**
 * Simulate captcha
 */
async function simulateCaptcha() {
  const startTime = Date.now();
  let success = false;
  
  try {
    monitor.log('🛡️ Simulating captcha...');
    await state.page.evaluate(() => {
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
    await state.page.evaluate(() => {
      const captcha = document.getElementById('captcha');
      if (captcha) captcha.remove();
    });
    
    success = true;
    monitor.log('✅ Captcha simulation complete');
  } catch (error) {
    monitor.log(`❌ Captcha simulation error: ${error.message}`);
    throw error;
  } finally {
    monitor.trackRequest('captcha', success, Date.now() - startTime, {
      error: success ? null : 'Captcha simulation failed'
    });
  }
}

/**
 * Test successful request
 */
async function testSuccess() {
  const startTime = Date.now();
  let success = false;
  
  try {
    monitor.log('✅ Testing successful request...');
    await state.page.goto('https://kwork.ru', { 
      waitUntil: 'domcontentloaded',
      timeout: 30000 
    });
    
    // Verify we're on the Kwork homepage
    const title = await state.page.title();
    success = title.includes('Kwork');
    
    if (success) {
      monitor.log('✅ Success test passed');
    } else {
      throw new Error('Unexpected page title: ' + title);
    }
  } catch (error) {
    monitor.log(`❌ Success test failed: ${error.message}`);
    throw error;
  } finally {
    monitor.trackRequest('success', success, Date.now() - startTime, {
      error: success ? null : 'Success test failed'
    });
  }
}

/**
 * Run a test scenario
 */
async function runScenario(scenario) {
  monitor.log(`\n=== Running scenario: ${scenario} ===`);
  
  try {
    // Check rate limit
    const waitTime = checkRateLimit();
    if (waitTime > 0) {
      monitor.log(`⚠️ Rate limit reached. Waiting ${Math.ceil(waitTime/1000)} seconds...`);
      await new Promise(resolve => setTimeout(resolve, waitTime));
    }
    
    // Run the scenario
    switch (scenario) {
      case 'network_failure':
        await simulateNetworkFailure();
        break;
      case 'timeout':
        await simulateTimeout();
        break;
      case 'captcha':
        await simulateCaptcha();
        break;
      case 'success':
        await testSuccess();
        break;
      default:
        throw new Error(`Unknown scenario: ${scenario}`);
    }
    
    state.stats.scenariosPassed++;
    return true;
  } catch (error) {
    state.stats.scenariosFailed++;
    state.stats.errors.push({
      scenario,
      time: new Date().toISOString(),
      error: error.message,
      stack: error.stack
    });
    
    // Take screenshot on error
    try {
      const screenshotDir = path.join(__dirname, 'screenshots');
      if (!fs.existsSync(screenshotDir)) {
        fs.mkdirSync(screenshotDir, { recursive: true });
      }
      
      const screenshotPath = path.join(screenshotDir, `error-${Date.now()}.png`);
      await state.page.screenshot({ path: screenshotPath });
      monitor.log(`📸 Screenshot saved to ${screenshotPath}`);
    } catch (screenshotError) {
      monitor.log(`❌ Failed to take screenshot: ${screenshotError.message}`);
    }
    
    return false;
  } finally {
    state.stats.scenariosRun++;
  }
}

/**
 * Generate test report
 */
function generateReport() {
  const report = {
    timestamp: new Date().toISOString(),
    duration: (Date.now() - state.startTime) / 1000,
    stats: {
      ...state.stats,
      successRate: (state.stats.scenariosPassed / state.stats.scenariosRun * 100).toFixed(2) + '%'
    },
    rateLimit: {
      hits: state.rateLimit.count,
      limit: CONFIG.RATE_LIMIT.requests,
      window: CONFIG.RATE_LIMIT.perMinutes + ' minutes'
    },
    errors: state.stats.errors,
    recommendations: []
  };
  
  // Add recommendations
  if (state.stats.scenariosFailed > 0) {
    report.recommendations.push({
      type: 'warning',
      message: `${state.stats.scenariosFailed} scenarios failed`,
      action: 'Review error logs and screenshots for details'
    });
  }
  
  if (state.rateLimit.count >= CONFIG.RATE_LIMIT.requests) {
    report.recommendations.push({
      type: 'warning',
      message: 'Rate limit was hit',
      action: 'Consider increasing rate limit or adding delays between requests'
    });
  }
  
  // Save report to file
  const reportDir = path.join(__dirname, 'reports');
  if (!fs.existsSync(reportDir)) {
    fs.mkdirSync(reportDir, { recursive: true });
  }
  
  const reportFile = path.join(reportDir, `stress-test-report-${Date.now()}.json`);
  fs.writeFileSync(reportFile, JSON.stringify(report, null, 2));
  
  monitor.log(`📊 Test report saved to ${reportFile}`);
  
  // Print summary
  console.log('\n=== Test Summary ===');
  console.log(`Duration: ${report.duration} seconds`);
  console.log(`Scenarios run: ${report.stats.scenariosRun}`);
  console.log(`Passed: ${report.stats.scenariosPassed}`);
  console.log(`Failed: ${report.stats.scenariosFailed}`);
  console.log(`Success rate: ${report.stats.successRate}`);
  console.log(`Rate limit hits: ${report.rateLimit.hits}/${report.rateLimit.limit} per ${report.rateLimit.window}`);
  
  return report;
}

/**
 * Main test runner
 */
async function runTests() {
  state.startTime = Date.now();
  state.isRunning = true;
  
  // Initialize browser
  try {
    state.browser = await chromium.launch({
      headless: true,
      timeout: 60000
    });
    
    const context = await state.browser.newContext({
      viewport: { width: 1280, height: 1024 },
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
      ignoreHTTPSErrors: true
    });
    
    state.page = await context.newPage();
    monitor.startSession();
    
    // Run test scenarios in fixed number of cycles
    for (let cycle = 1; cycle <= CONFIG.MAX_RUNS; cycle++) {
      monitor.log(`🚀 Starting test cycle ${cycle} of ${CONFIG.MAX_RUNS}`);
      
      // Run each scenario in sequence
      for (const scenario of CONFIG.SCENARIOS) {
        if (!state.isRunning) break;
        
        monitor.log(`🔄 Running scenario: ${scenario}`);
        await runScenario(scenario);
        
        // Fixed delay between scenarios
        if (scenario !== CONFIG.SCENARIOS[CONFIG.SCENARIOS.length - 1]) {
          await new Promise(resolve => setTimeout(resolve, CONFIG.SCENARIO_DELAY));
        }
      }
      
      monitor.log(`✅ Completed test cycle ${cycle} of ${CONFIG.MAX_RUNS}`);
      
      // Small delay between cycles
      if (cycle < CONFIG.MAX_RUNS) {
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
    }
    
  } catch (error) {
    monitor.log(`❌ Test runner error: ${error.message}`);
    console.error(error);
  } finally {
    state.isRunning = false;
    monitor.endSession();
    
    if (state.browser) {
      await state.browser.close();
    }
    
    generateReport();
    monitor.log('🏁 Test completed');
  }
}

// Handle process termination
process.on('SIGINT', async () => {
  monitor.log('🛑 Received SIGINT, stopping tests...');
  state.isRunning = false;
  
  // Give some time for cleanup
  setTimeout(async () => {
    if (state.browser) {
      await state.browser.close();
    }
    process.exit(0);
  }, 5000);
});

// Start the tests
monitor.log('🚀 Starting Kwork Bridge Stress Tests');
runTests().catch(error => {
  monitor.log(`❌ Fatal error: ${error.message}`);
  console.error(error);
  process.exit(1);
});
