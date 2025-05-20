const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
const monitor = require('./monitor');
const CONFIG = require('../tests/config');

class MonitoredBridge {
  constructor() {
    this.browser = null;
    this.page = null;
    this.context = null;
    this.isInitialized = false;
    this.sessionId = null;
    this.metrics = {
      requests: 0,
      errors: 0,
      rateLimitsHit: 0,
      sessionStart: null,
      lastRequest: null
    };
  }

  /**
   * Initialize the browser and page
   */
  async initialize() {
    if (this.isInitialized) return;

    try {
      monitor.log('Initializing monitored bridge...');
      
      this.browser = await chromium.launch({
        headless: CONFIG.BROWSER.headless,
        timeout: CONFIG.BROWSER.timeout
      });

      this.context = await this.browser.newContext({
        viewport: CONFIG.BROWSER.viewport,
        userAgent: CONFIG.BROWSER.userAgent,
        ignoreHTTPSErrors: CONFIG.BROWSER.ignoreHTTPSErrors
      });

      this.page = await this.context.newPage();
      this.isInitialized = true;
      this.metrics.sessionStart = Date.now();
      this.sessionId = `session-${Date.now()}`;
      
      monitor.startSession(this.sessionId);
      monitor.log('Monitored bridge initialized');
      
      return true;
    } catch (error) {
      monitor.log(`❌ Failed to initialize monitored bridge: ${error.message}`);
      throw error;
    }
  }

  /**
   * Make a request to Kwork with monitoring
   */
  async makeRequest(url, options = {}) {
    if (!this.isInitialized) {
      await this.initialize();
    }

    const startTime = Date.now();
    let success = false;
    let response = null;
    let error = null;

    try {
      monitor.log(`🌐 Making request to: ${url}`);
      
      // Track rate limiting
      const waitTime = this.checkRateLimit();
      if (waitTime > 0) {
        monitor.log(`⚠️ Rate limit reached. Waiting ${Math.ceil(waitTime/1000)} seconds...`);
        monitor.trackRateLimit();
        await new Promise(resolve => setTimeout(resolve, waitTime));
      }

      // Make the request
      response = await this.page.goto(url, {
        waitUntil: 'domcontentloaded',
        timeout: options.timeout || 30000,
        ...options
      });

      // Check for errors
      if (!response.ok()) {
        throw new Error(`Request failed with status ${response.status()}: ${response.statusText()}`);
      }

      success = true;
      this.metrics.requests++;
      this.metrics.lastRequest = Date.now();
      
      monitor.trackRequest('kwork_request', true, Date.now() - startTime, {
        url,
        status: response.status(),
        method: options.method || 'GET'
      });
      
      return response;
    } catch (err) {
      error = err;
      this.metrics.errors++;
      
      monitor.trackRequest('kwork_request', false, Date.now() - startTime, {
        url,
        error: err.message,
        status: response?.status() || 0
      });
      
      // Take screenshot on error
      try {
        const screenshotPath = path.join(CONFIG.PATHS.screenshots, `error-${Date.now()}.png`);
        await this.page.screenshot({ path: screenshotPath });
        monitor.log(`📸 Screenshot saved to ${screenshotPath}`);
      } catch (screenshotError) {
        monitor.log(`❌ Failed to take screenshot: ${screenshotError.message}`);
      }
      
      throw error;
    }
  }

  /**
   * Check and enforce rate limiting
   */
  checkRateLimit() {
    const now = Date.now();
    
    // Reset counter if time window has passed
    if (now > (this.metrics.rateLimitReset || 0)) {
      this.metrics.rateLimitCount = 0;
      this.metrics.rateLimitReset = now + (CONFIG.RATE_LIMIT.perMinutes * 60 * 1000);
    }
    
    // Check if rate limit exceeded
    if (this.metrics.rateLimitCount >= CONFIG.RATE_LIMIT.requests) {
      const waitTime = this.metrics.rateLimitReset - now;
      this.metrics.rateLimitsHit++;
      return waitTime;
    }
    
    this.metrics.rateLimitCount = (this.metrics.rateLimitCount || 0) + 1;
    return 0;
  }

  /**
   * Get current metrics
   */
  getMetrics() {
    return {
      ...this.metrics,
      uptime: this.metrics.sessionStart ? Date.now() - this.metrics.sessionStart : 0,
      requestsPerMinute: this.calculateRate(this.metrics.requests, this.metrics.sessionStart),
      errorRate: this.metrics.requests > 0 
        ? (this.metrics.errors / this.metrics.requests) * 100 
        : 0
    };
  }

  /**
   * Calculate rate per minute
   */
  calculateRate(count, startTime) {
    if (!startTime) return 0;
    const minutes = (Date.now() - startTime) / (1000 * 60);
    return minutes > 0 ? (count / minutes).toFixed(2) : 0;
  }

  /**
   * Clean up resources
   */
  async close() {
    if (this.browser) {
      monitor.log('Closing monitored bridge...');
      await this.browser.close();
      this.isInitialized = false;
      this.metrics.sessionEnd = Date.now();
      
      monitor.endSession(this.sessionId, {
        ...this.getMetrics(),
        sessionDuration: this.metrics.sessionEnd - this.metrics.sessionStart
      });
      
      monitor.log('Monitored bridge closed');
    }
  }
}

// Create a singleton instance
const monitoredBridge = new MonitoredBridge();

// Handle process termination
process.on('SIGINT', async () => {
  monitor.log('🛑 Received SIGINT, cleaning up...');
  await monitoredBridge.close();
  process.exit(0);
});

module.exports = monitoredBridge;
