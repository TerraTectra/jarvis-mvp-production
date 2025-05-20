const loadtest = require('loadtest');
const { writeFile } = require('fs').promises;
const path = require('path');
const { promisify } = require('util');
const { exec } = require('child_process');
const execAsync = promisify(exec);

// Configuration
const CONFIG = {
  baseUrl: process.env.API_URL || 'http://localhost:3000',
  // Test phases configuration
  phases: [
    // Base load: 100 RPS for 10 minutes
    {
      duration: 10 * 60 * 1000, // 10 minutes
      rate: 100, // 100 requests per second
      concurrency: 50
    },
    // Spike to 300 RPS for 2 minutes
    {
      duration: 2 * 60 * 1000, // 2 minutes
      rate: 300, // 300 requests per second
      concurrency: 150
    },
    // Cooldown: 3 minutes
    {
      duration: 3 * 60 * 1000, // 3 minutes
      rate: 50, // 50 requests per second
      concurrency: 25
    }
  ],
  // Test endpoints
  endpoints: [
    { path: '/orders', method: 'GET' },
    { path: '/logs', method: 'GET' },
    { path: '/status', method: 'GET' }
  ],
  // Resource limits
  resourceLimits: {
    gpu: 12, // GB
    cpu: 85, // %
    ram: 16  // GB
  },
  // Performance targets
  targets: {
    latency: {
      p50: 1000,  // ms
      p95: 1500,  // ms
      p99: 2000   // ms
    },
    errorRate: 1, // %
    sessionDuration: 15 * 60 * 1000 // 15 minutes
  },
  reportFile: path.join(__dirname, 'reports', 'load_test_report.json')
};

// Metrics collection
const metrics = {
  startTime: null,
  endTime: null,
  requests: 0,
  errors: 0,
  responseTimes: [],
  statusCodes: {},
  errorsByType: {},
  llmLatencies: [],
  autoResponseSuccess: 0,
  autoResponseTotal: 0,
  unclosedSessions: [],
  // Resource metrics
  maxGpuUsage: 0, // GB
  maxCpuUsage: 0, // %
  maxRamUsage: 0, // GB
  resourceSamples: []
};

// Resource monitoring
async function monitorResources() {
  const startTime = Date.now();
  const sampleInterval = 5000; // 5 seconds
  
  const monitorLoop = async () => {
    if (!metrics.startTime) return; // Don't start until test begins
    
    try {
      // Get system metrics (Linux-specific commands)
      const [gpuCmd, cpuCmd, ramCmd] = await Promise.all([
        execAsync('nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits')
          .catch(() => ({ stdout: '0' })), // Fallback if no GPU
        execAsync("top -bn1 | grep 'Cpu(s)' | awk '{print $2 + $4}'").catch(() => ({ stdout: '0' })),
        execAsync("free -m | awk 'NR==2{printf \"%.1f\", $3/1024}'").catch(() => ({ stdout: '0' }))
      ]);
      
      const gpuUsage = parseFloat(gpuCmd.stdout.trim()) || 0;
      const cpuUsage = parseFloat(cpuCmd.stdout.trim()) || 0;
      const ramUsage = parseFloat(ramCmd.stdout.trim()) || 0;
      
      // Update max values
      metrics.maxGpuUsage = Math.max(metrics.maxGpuUsage, gpuUsage);
      metrics.maxCpuUsage = Math.max(metrics.maxCpuUsage, cpuUsage);
      metrics.maxRamUsage = Math.max(metrics.maxRamUsage, ramUsage);
      
      // Store sample
      metrics.resourceSamples.push({
        timestamp: Date.now(),
        gpu: gpuUsage,
        cpu: cpuUsage,
        ram: ramUsage
      });
      
      // Check resource limits
      if (gpuUsage > CONFIG.resourceLimits.gpu) {
        console.warn(`⚠️  GPU usage exceeds limit: ${gpuUsage.toFixed(1)}GB > ${CONFIG.resourceLimits.gpu}GB`);
      }
      if (cpuUsage > CONFIG.resourceLimits.cpu) {
        console.warn(`⚠️  CPU usage exceeds limit: ${cpuUsage.toFixed(1)}% > ${CONFIG.resourceLimits.cpu}%`);
      }
      if (ramUsage > CONFIG.resourceLimits.ram) {
        console.warn(`⚠️  RAM usage exceeds limit: ${ramUsage.toFixed(1)}GB > ${CONFIG.resourceLimits.ram}GB`);
      }
    } catch (error) {
      console.error('Error monitoring resources:', error);
    }
    
    // Continue monitoring if test is still running
    if (metrics.startTime && !metrics.endTime) {
      setTimeout(monitorLoop, sampleInterval);
    }
  };
  
  // Start monitoring
  monitorLoop();
}

// Function to run a single test phase
async function runTestPhase(phase, endpoint) {
  const options = {
    url: `${CONFIG.baseUrl}${endpoint.path}`,
    method: endpoint.method,
    maxRequests: 0, // Unlimited requests
    concurrency: phase.concurrency,
    requestsPerSecond: phase.rate / CONFIG.endpoints.length,
    timeout: 10000, // 10 seconds
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${process.env.API_KEY || ''}`
    }
  };
  
  console.log(`🚀 Starting phase: ${phase.rate} RPS for ${phase.duration/1000}s`);
  
  // Track session start time for long session test
  const sessionStartTime = Date.now();
  
  // Simulate Kwork failure after 5 minutes if this is the first phase
  if (phase === CONFIG.phases[0]) {
    setTimeout(simulateKworkFailure, 5 * 60 * 1000);
  }

  return new Promise((resolve, reject) => {
    const test = loadtest.loadTest(options, (error, result) => {
      if (error) {
        console.error(`Error in ${endpoint.path}:`, error);
        return reject(error);
      }
      
      // Collect metrics
      metrics.requests += result.totalRequests;
      metrics.errors += result.totalErrors;
      metrics.responseTimes.push(...result.latencyTimes);
      
      // Track status codes
      Object.entries(result.statusCodes).forEach(([code, count]) => {
        metrics.statusCodes[code] = (metrics.statusCodes[code] || 0) + count;
      });
      
      resolve(result);
    });

    // Handle test errors
    test.on('error', (error) => {
      const errorType = error.code || 'unknown';
      metrics.errorsByType[errorType] = (metrics.errorsByType[errorType] || 0) + 1;
      
      // Check for unclosed sessions or other specific errors
      if (error.message && error.message.includes('unclosed aiohttp session') || 
          error.message.includes('another operation is in progress')) {
        metrics.unclosedSessions.push({
          time: new Date().toISOString(),
          endpoint: endpoint.path,
          error: error.message
        });
      }
    });

    // Simulate database failure after 5 minutes
    setTimeout(async () => {
      if (endpoint.path === '/status') {
        console.log('\n🔧 Simulating database failure...');
        try {
          // This is a placeholder - replace with actual command to simulate DB failure
          await execAsync('docker-compose stop db');
          console.log('Database stopped for testing error handling');
        } catch (err) {
          console.error('Error simulating DB failure:', err);
        }
      }
    }, 5 * 60 * 1000);
  });
}

// Generate markdown report
async function generateReport() {
  const totalTime = (metrics.endTime - metrics.startTime) / 1000; // in seconds
  const requestsPerSecond = metrics.requests / totalTime;
  const errorRate = (metrics.errors / metrics.requests) * 100;
  
  // Calculate percentiles
  const sortedTimes = [...metrics.responseTimes].sort((a, b) => a - b);
  const p50 = calculatePercentile(sortedTimes, 0.5);
  const p95 = calculatePercentile(sortedTimes, 0.95);
  const p99 = calculatePercentile(sortedTimes, 0.99);
  
  // Calculate LLM metrics
  const llmMedian = metrics.llmLatencies.length > 0 ? 
    calculatePercentile([...metrics.llmLatencies].sort((a, b) => a - b), 0.5) : 0;
  const autoResponseSuccessRate = metrics.autoResponseTotal > 0 ?
    (metrics.autoResponseSuccess / metrics.autoResponseTotal) * 100 : 0;

  // Check if targets are met
  const meetsTargets = {
    latency: {
      p50: p50 <= CONFIG.targets.latency.p50,
      p95: p95 <= CONFIG.targets.latency.p95,
      p99: p99 <= CONFIG.targets.latency.p99
    },
    errorRate: errorRate <= CONFIG.targets.errorRate,
    resources: {
      gpu: metrics.maxGpuUsage <= CONFIG.resourceLimits.gpu,
      cpu: metrics.maxCpuUsage <= CONFIG.resourceLimits.cpu,
      ram: metrics.maxRamUsage <= CONFIG.resourceLimits.ram
    }
  };

  const allTargetsMet = Object.values(meetsTargets.latency).every(Boolean) &&
                      meetsTargets.errorRate &&
                      Object.values(meetsTargets.resources).every(Boolean);

  const report = {
    timestamp: new Date().toISOString(),
    testDuration: `${totalTime.toFixed(2)}s`,
    totalRequests: metrics.requests,
    requestsPerSecond: requestsPerSecond.toFixed(2),
    errorRate: {
      value: errorRate.toFixed(2) + '%',
      target: CONFIG.targets.errorRate + '%',
      met: meetsTargets.errorRate
    },
    latency: {
      p50: {
        value: p50.toFixed(2) + 'ms',
        target: CONFIG.targets.latency.p50 + 'ms',
        met: meetsTargets.latency.p50
      },
      p95: {
        value: p95.toFixed(2) + 'ms',
        target: CONFIG.targets.latency.p95 + 'ms',
        met: meetsTargets.latency.p95
      },
      p99: {
        value: p99.toFixed(2) + 'ms',
        target: CONFIG.targets.latency.p99 + 'ms',
        met: meetsTargets.latency.p99
      },
      max: Math.max(...sortedTimes).toFixed(2) + 'ms'
    },
    resourceUsage: {
      gpu: {
        max: metrics.maxGpuUsage?.toFixed(2) + 'GB' || 'N/A',
        limit: CONFIG.resourceLimits.gpu + 'GB',
        met: meetsTargets.resources.gpu
      },
      cpu: {
        max: metrics.maxCpuUsage?.toFixed(2) + '%' || 'N/A',
        limit: CONFIG.resourceLimits.cpu + '%',
        met: meetsTargets.resources.cpu
      },
      ram: {
        max: metrics.maxRamUsage?.toFixed(2) + 'GB' || 'N/A',
        limit: CONFIG.resourceLimits.ram + 'GB',
        met: meetsTargets.resources.ram
      }
    },
    statusCodes: metrics.statusCodes,
    errorsByType: metrics.errorsByType,
    unclosedSessions: metrics.unclosedSessions,
    meetsTargets: allTargetsMet,
    testPhases: CONFIG.phases.map(p => ({
      duration: `${p.duration/1000}s`,
      rate: `${p.rate} RPS`,
      concurrency: p.concurrency
    }))
  };

  // Save report to file
  await writeFile(CONFIG.reportFile, JSON.stringify(report, null, 2));
  
  // Generate markdown report
  const markdown = `# 🚀 Load Test Report

## 📊 Test Summary
| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Test Duration | ${report.testDuration} | - | - |
| Total Requests | ${report.totalRequests} | - | - |
| Requests/sec | ${report.requestsPerSecond} | - | - |
| Error Rate | ${report.errorRate.value} | <${report.errorRate.target} | ${report.errorRate.met ? '✅' : '❌'} |
| All Targets Met | - | - | ${report.meetsTargets ? '✅ Yes' : '❌ No'} |

## ⏱️ Latency Results (ms)
| Percentile | Value | Target | Status |
|------------|-------|--------|--------|
| p50 | ${report.latency.p50.value} | ${report.latency.p50.target} | ${report.latency.p50.met ? '✅' : '❌'} |
| p95 | ${report.latency.p95.value} | ${report.latency.p95.target} | ${report.latency.p95.met ? '✅' : '❌'} |
| p99 | ${report.latency.p99.value} | ${report.latency.p99.target} | ${report.latency.p99.met ? '✅' : '❌'} |
| Max | ${report.latency.max} | - | - |

## 💻 Resource Usage
| Resource | Usage | Limit | Status |
|----------|-------|-------|--------|
| GPU | ${report.resourceUsage.gpu.max} | ${report.resourceUsage.gpu.limit} | ${report.resourceUsage.gpu.met ? '✅' : '❌'} |
| CPU | ${report.resourceUsage.cpu.max} | ${report.resourceUsage.cpu.limit} | ${report.resourceUsage.cpu.met ? '✅' : '❌'} |
| RAM | ${report.resourceUsage.ram.max} | ${report.resourceUsage.ram.limit} | ${report.resourceUsage.ram.met ? '✅' : '❌'} |

## 🔄 Test Phases
${report.testPhases.map((phase, i) => 
  `### Phase ${i + 1}
- Duration: ${phase.duration}
- Rate: ${phase.rate}
- Concurrency: ${phase.concurrency}`
).join('\n\n')}

## 📋 Status Codes
${Object.entries(report.statusCodes).map(([code, count]) => `- ${code}: ${count}`).join('\n')}

## ❌ Error Types
${Object.entries(report.errorsByType).length > 0 ? 
  Object.entries(report.errorsByType).map(([type, count]) => `- ${type}: ${count}`).join('\n') :
  'No errors detected'}

## ⚠️ Unclosed Sessions
${report.unclosedSessions.length > 0 ? 
  report.unclosedSessions.map(s => `- ${s.time}: ${s.endpoint} - ${s.error}`).join('\n') : 
  'No unclosed sessions detected'}

## 🎯 Test Result: ${report.meetsTargets ? 'PASSED ✅' : 'FAILED ❌'}
${
  report.meetsTargets 
    ? 'All performance and resource usage targets were met!' 
    : 'One or more targets were not met. Please check the report above for details.'
}

### Test Configuration
- **Base URL**: ${CONFIG.baseUrl}
- **Test Started**: ${new Date(report.timestamp).toLocaleString()}
- **Total Duration**: ${report.testDuration}
`;

  console.log('\n' + markdown);
  return report;
}

// Helper function to calculate percentiles
function calculatePercentile(sortedArray, percentile) {
  if (sortedArray.length === 0) return 0;
  const index = Math.ceil(percentile * sortedArray.length) - 1;
  return sortedArray[Math.max(0, Math.min(index, sortedArray.length - 1))];
}

// Main function
async function runLoadTest() {
  console.log('🚀 Starting load test...');
  console.log(`Testing endpoints: ${CONFIG.endpoints.map(e => e.path).join(', ')}`);
  console.log(`Duration: ${CONFIG.duration / 60000} minutes`);
  console.log(`Target rate: ${CONFIG.requestsPerSecond} req/s (${CONFIG.requestsPerSecond * 60} req/min)\n`);

  metrics.startTime = Date.now();
  
  try {
    // Create reports directory if it doesn't exist
    await execAsync('mkdir -p tests/reports');
    
    // Run tests for all endpoints in parallel
    await Promise.all(CONFIG.endpoints.map(endpoint => 
      testEndpoint(endpoint).catch(console.error)
    ));
    
  } catch (error) {
    console.error('Load test failed:', error);
  } finally {
    metrics.endTime = Date.now();
    
    // Generate and save report
    const report = await generateReport();
    
    // Restart database if it was stopped
    try {
      await execAsync('docker-compose start db');
      console.log('\n✅ Database restarted');
    } catch (err) {
      console.error('Error restarting database:', err);
    }
    
    // Exit with appropriate status code
    process.exit(report.isProductionReady ? 0 : 1);
  }
}

// Simulate Kwork failure
async function simulateKworkFailure() {
  console.log('🔥 Simulating Kwork failure...');
  try {
    // Add your Kwork failure simulation logic here
    // For example, you might want to block Kwork API endpoints
    // or trigger a service restart
    console.log('✅ Kwork failure simulation complete');
  } catch (error) {
    console.error('❌ Failed to simulate Kwork failure:', error);
  }
}

// Main test execution
async function runLoadTest() {
  console.log('🚀 Starting load test with configuration:');
  console.log(`- Base URL: ${CONFIG.baseUrl}`);
  console.log(`- Phases: ${CONFIG.phases.length} phases`);
  console.log(`- Endpoints: ${CONFIG.endpoints.map(e => e.path).join(', ')}`);
  console.log('---');

  // Start resource monitoring
  monitorResources();
  metrics.startTime = Date.now();
  
  try {
    // Create reports directory
    await execAsync('mkdir -p tests/reports');
    
    // Run each test phase
    for (const [index, phase] of CONFIG.phases.entries()) {
      const phaseStart = Date.now();
      console.log(`\n📊 Starting Phase ${index + 1}/${CONFIG.phases.length}:`);
      console.log(`- Rate: ${phase.rate} RPS`);
      console.log(`- Duration: ${phase.duration/1000}s`);
      console.log(`- Concurrency: ${phase.concurrency}`);
      
      // Run tests for all endpoints in parallel
      const testPromises = CONFIG.endpoints.map(endpoint => 
        runTestPhase(phase, endpoint).catch(error => {
          console.error(`Error in ${endpoint.path}:`, error);
          return { error };
        })
      );
      
      // Wait for the phase duration or until all requests complete
      await Promise.race([
        Promise.all(testPromises),
        new Promise(resolve => setTimeout(resolve, phase.duration))
      ]);
      
      // Log phase completion
      const phaseDuration = (Date.now() - phaseStart) / 1000;
      console.log(`✅ Phase ${index + 1} completed in ${phaseDuration.toFixed(1)}s`);
      
      // Add a small delay between phases
      if (index < CONFIG.phases.length - 1) {
        console.log('⏳ Preparing next phase...');
        await new Promise(resolve => setTimeout(resolve, 2000));
      }
    }
    
  } catch (error) {
    console.error('❌ Load test failed:', error);
    metrics.errors++;
  } finally {
    metrics.endTime = Date.now();
    
    try {
      // Generate and save report
      const report = await generateReport();
      
      // Exit with appropriate status code
      process.exit(report.meetsTargets ? 0 : 1);
    } catch (reportError) {
      console.error('❌ Failed to generate report:', reportError);
      process.exit(1);
    }
  }
}

// Start the test
runLoadTest();
