const fs = require('fs');
const path = require('path');
const { logWithTimestamp } = require('./kwork_node_bridge');

class BridgeMonitor {
  constructor() {
    this.metrics = {
      startTime: Date.now(),
      requests: [],
      errors: [],
      sessions: [],
      ordersProcessed: 0,
      rateLimitsHit: 0,
      retries: 0,
      lastSessionStart: null,
      currentSessionStart: null
    };
    
    this.logFile = path.join(__dirname, '..', 'logs', 'bridge-monitor.log');
    this.metricsFile = path.join(__dirname, '..', 'logs', 'bridge-metrics.json');
    
    // Ensure logs directory exists
    const logsDir = path.dirname(this.logFile);
    if (!fs.existsSync(logsDir)) {
      fs.mkdirSync(logsDir, { recursive: true });
    }
    
    // Initialize log file
    this.log(`🚀 Bridge Monitor started at ${new Date().toISOString()}`);
    this.saveMetrics();
  }
  
  log(message) {
    const timestamp = new Date().toISOString();
    const logMessage = `[${timestamp}] ${message}`;
    
    // Log to console
    logWithTimestamp(message);
    
    // Append to log file
    fs.appendFileSync(this.logFile, logMessage + '\n');
  }
  
  saveMetrics() {
    try {
      fs.writeFileSync(this.metricsFile, JSON.stringify(this.metrics, null, 2));
    } catch (error) {
      console.error('Failed to save metrics:', error);
    }
  }
  
  // Session tracking
  startSession() {
    this.metrics.lastSessionStart = this.metrics.currentSessionStart || Date.now();
    this.metrics.currentSessionStart = Date.now();
    
    this.metrics.sessions.push({
      start: this.metrics.currentSessionStart,
      end: null,
      duration: null
    });
    
    this.log(`🔄 Session started`);
    this.saveMetrics();
  }
  
  endSession() {
    if (!this.metrics.currentSessionStart) return;
    
    const session = this.metrics.sessions[this.metrics.sessions.length - 1];
    if (session) {
      session.end = Date.now();
      session.duration = session.end - session.start;
      
      this.log(`🛑 Session ended after ${(session.duration / 1000).toFixed(2)}s`);
      this.log(`📊 Session stats: ${this.getSessionStats()}`);
    }
    
    this.metrics.currentSessionStart = null;
    this.saveMetrics();
  }
  
  // Request tracking
  trackRequest(type, success, duration, metadata = {}) {
    const request = {
      timestamp: Date.now(),
      type,
      success,
      duration,
      ...metadata
    };
    
    this.metrics.requests.push(request);
    
    if (!success) {
      this.metrics.errors.push({
        ...request,
        error: metadata.error || 'Unknown error'
      });
    }
    
    // Keep only the last 1000 requests
    if (this.metrics.requests.length > 1000) {
      this.metrics.requests = this.metrics.requests.slice(-1000);
    }
    
    this.saveMetrics();
    return request;
  }
  
  // Order processing
  trackOrderProcessed(orderId) {
    this.metrics.ordersProcessed++;
    this.log(`✅ Order processed: ${orderId}`);
    this.saveMetrics();
  }
  
  // Rate limiting
  trackRateLimit() {
    this.metrics.rateLimitsHit++;
    this.log('⚠️ Rate limit hit');
    this.saveMetrics();
  }
  
  // Retry tracking
  trackRetry(operation, attempt, maxAttempts, error) {
    this.metrics.retries++;
    this.log(`🔄 Retry ${attempt}/${maxAttempts} for ${operation}: ${error?.message || 'Unknown error'}`);
    this.saveMetrics();
  }
  
  // Statistics
  getSessionStats() {
    const now = Date.now();
    const duration = now - (this.metrics.currentSessionStart || now);
    const requests = this.metrics.requests.filter(r => 
      r.timestamp >= (this.metrics.currentSessionStart || 0)
    );
    
    const successful = requests.filter(r => r.success).length;
    const failed = requests.length - successful;
    const successRate = requests.length > 0 ? (successful / requests.length) * 100 : 0;
    
    return `${requests.length} requests (${successful}✅ ${failed}❌ ${successRate.toFixed(1)}% success)`;
  }
  
  getOverallStats() {
    const now = Date.now();
    const duration = now - this.metrics.startTime;
    const hours = duration / (1000 * 60 * 60);
    
    const requests = this.metrics.requests;
    const successful = requests.filter(r => r.success).length;
    const failed = requests.length - successful;
    const successRate = requests.length > 0 ? (successful / requests.length) * 100 : 0;
    
    const ordersPerHour = hours > 0 ? (this.metrics.ordersProcessed / hours).toFixed(2) : 0;
    const avgRequestTime = requests.length > 0 
      ? (requests.reduce((sum, r) => sum + (r.duration || 0), 0) / requests.length).toFixed(2)
      : 0;
    
    const sessionDurations = this.metrics.sessions
      .filter(s => s.duration !== null)
      .map(s => s.duration);
    
    const avgSessionDuration = sessionDurations.length > 0
      ? (sessionDurations.reduce((a, b) => a + b, 0) / sessionDurations.length / 1000).toFixed(2)
      : 0;
    
    return {
      uptime: (duration / (1000 * 60 * 60)).toFixed(2) + ' hours',
      totalRequests: requests.length,
      successfulRequests: successful,
      failedRequests: failed,
      successRate: successRate.toFixed(2) + '%',
      ordersProcessed: this.metrics.ordersProcessed,
      ordersPerHour: ordersPerHour,
      averageRequestTime: avgRequestTime + 'ms',
      rateLimitsHit: this.metrics.rateLimitsHit,
      retries: this.metrics.retries,
      sessions: this.metrics.sessions.length,
      averageSessionDuration: avgSessionDuration + 's'
    };
  }
  
  // Generate report
  generateReport() {
    const stats = this.getOverallStats();
    const report = {
      timestamp: new Date().toISOString(),
      metrics: stats,
      recentErrors: this.metrics.errors.slice(-10).map(e => ({
        timestamp: new Date(e.timestamp).toISOString(),
        type: e.type,
        error: e.error
      })),
      recommendations: this.generateRecommendations()
    };
    
    return report;
  }
  
  generateRecommendations() {
    const recommendations = [];
    const stats = this.getOverallStats();
    
    if (stats.failedRequests > 0) {
      const errorRate = (stats.failedRequests / stats.totalRequests) * 100;
      if (errorRate > 10) {
        recommendations.push({
          issue: 'High error rate',
          details: `Error rate is ${errorRate.toFixed(1)}% which is above the 10% threshold`,
          suggestion: 'Investigate the root cause of the errors in the logs'
        });
      }
    }
    
    if (this.metrics.rateLimitsHit > 0) {
      recommendations.push({
        issue: 'Rate limiting detected',
        details: `Rate limit was hit ${this.metrics.rateLimitsHit} times`,
        suggestion: 'Consider implementing exponential backoff or reducing request frequency'
      });
    }
    
    if (stats.retries > 0) {
      recommendations.push({
        issue: 'Retries detected',
        details: `${stats.retries} operations were retried`,
        suggestion: 'Review the retry logic and error handling for flaky operations'
      });
    }
    
    if (recommendations.length === 0) {
      recommendations.push({
        status: 'All systems nominal',
        details: 'No critical issues detected',
        suggestion: 'Continue monitoring for any anomalies'
      });
    }
    
    return recommendations;
  }
}

// Create a singleton instance
const monitor = new BridgeMonitor();

// Handle process termination
process.on('SIGINT', () => {
  monitor.log('🛑 Received SIGINT, saving metrics...');
  monitor.endSession();
  monitor.saveMetrics();
  process.exit(0);
});

// Auto-save metrics periodically
setInterval(() => {
  monitor.saveMetrics();
}, 5 * 60 * 1000); // Every 5 minutes

module.exports = monitor;
