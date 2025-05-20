module.exports = {
  // Test scenarios configuration
  SCENARIOS: {
    network_failure: {
      name: 'Network Failure',
      description: 'Simulates network disconnection during operation',
      enabled: true,
      weight: 1,
      timeout: 30000 // ms
    },
    timeout: {
      name: 'Request Timeout',
      description: 'Simulates server not responding within expected time',
      enabled: true,
      weight: 1,
      timeout: 60000
    },
    captcha: {
      name: 'CAPTCHA Challenge',
      description: 'Simulates encountering a CAPTCHA',
      enabled: true,
      weight: 1,
      timeout: 30000
    },
    success: {
      name: 'Successful Request',
      description: 'Standard successful request',
      enabled: true,
      weight: 3, // More weight for successful scenarios
      timeout: 30000
    }
  },
  
  // Test runner configuration
  TEST_DURATION: 30 * 60 * 1000, // 30 minutes
  MIN_DELAY: 2000, // 2 seconds
  MAX_DELAY: 10000, // 10 seconds
  
  // Rate limiting
  RATE_LIMIT: {
    requests: 30,      // Max requests
    perMinutes: 10,    // Per 10 minutes
    cooldown: 60000    // 1 minute cooldown when limit hit
  },
  
  // Browser configuration
  BROWSER: {
    headless: true,
    timeout: 60000,
    viewport: { width: 1280, height: 1024 },
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    ignoreHTTPSErrors: true
  },
  
  // Paths
  PATHS: {
    screenshots: 'test-results/screenshots',
    reports: 'test-results/reports',
    logs: 'test-results/logs'
  },
  
  // Kwork specific selectors
  SELECTORS: {
    // Order list page
    ORDERS_LIST: '.js-order-list',
    ORDER_ITEM: '.wants-card',
    ORDER_TITLE: '.wants-card__header-title',
    ORDER_DESCRIPTION: '.wants-card__description-text',
    ORDER_PRICE: '.wants-card__header-price',
    ORDER_LINK: '.wants-card__header-title a',
    
    // Login page
    USERNAME_INPUT: 'input[name="login"]',
    PASSWORD_INPUT: 'input[name="password"]',
    SUBMIT_BUTTON: 'button[type="submit"]',
    LOGIN_ERROR: '.js-login-error',
    
    // Common
    PROFILE_MENU: '.header-profile-menu',
    CAPTCHA: '.captcha',
    NO_ORDERS_MESSAGE: '.wants-list__empty',
    NEXT_PAGE: '.pager__item:last-child:not(.is-disabled)'
  },
  
  // URLs
  URLS: {
    BASE: 'https://kwork.ru',
    LOGIN: 'https://kwork.ru/user/login',
    ORDERS: 'https://kwork.ru/projects',
    PROFILE: 'https://kwork.ru/user/profile'
  }
};
