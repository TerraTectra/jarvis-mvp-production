#!/usr/bin/env node

// Log bridge start to stderr with timestamp
const logWithTimestamp = (...args) => {
  const timestamp = new Date().toISOString();
  console.error(`[${timestamp}]`, ...args);
};

// Export the function for use in other modules
module.exports = {
  logWithTimestamp,
  // Other exports will be added here
};

// Log bridge start
logWithTimestamp("🚀 Kwork bridge started — awaiting commands");
logWithTimestamp(`Node.js version: ${process.version}`);
logWithTimestamp(`Platform: ${process.platform} ${process.arch}`);
logWithTimestamp(`Current directory: ${process.cwd()}`);

// Log environment variables (safely)
const envVars = ['NODE_ENV', 'KWORK_USERNAME', 'KWORK_PASSWORD', 'KWORK_PINCODE'];
const envInfo = envVars.map(varName => `${varName}=${process.env[varName] ? '***' : 'not set'}`).join(', ');
logWithTimestamp(`Environment: ${envInfo}`);

/**
 * Node.js Bridge for Kwork API with Proxy and Captcha support
 * 
 * Accepts commands via stdin in JSON format
 * Returns responses via stdout in JSON format
 */

const Kwork = require('kwork-api');
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
require('dotenv').config();

// Don't show welcome message to avoid breaking JSON parsing
// process.stdout.write('Kwork Node Bridge with Proxy and Captcha support is ready\n');

// Конфигурация
const CONFIG = {
  // Пути
  SESSIONS_DIR: path.join(__dirname, '../data/sessions'),
  
  // Настройки сессии
  SESSION: {
    TTL: parseInt(process.env.SESSION_TTL || '900', 10), // 15 минут по умолчанию
    LAST_REFRESH_FILE: path.join(__dirname, '../data/last_refresh.json')
  },
  
  // Настройки браузера
  BROWSER: {
    headless: process.env.HEADLESS !== 'false',
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-accelerated-2d-canvas',
      '--no-first-run',
      '--no-zygote',
      '--single-process',
      '--disable-gpu',
      '--disable-extensions'
    ]
  },
  
  // Таймауты
  TIMEOUTS: {
    PAGE_LOAD: 30000,
    NAVIGATION: 60000,
    CAPTCHA_SOLVE: 120000
  },
  
  // Селекторы
  SELECTORS: {
    LOGIN_FORM: 'form[action*="login"]',
    USERNAME_INPUT: 'input[name="login"]',
    PASSWORD_INPUT: 'input[name="password"]',
    SUBMIT_BUTTON: 'button[type="submit"]',
    CAPTCHA_IFRAME: 'iframe[src*="recaptcha"]',
    CAPTCHA_CHECKBOX: '.recaptcha-checkbox',
    LOGIN_ERROR: '.error-message',
    AUTH_FORM: '.auth-form',
    PROFILE_MENU: '.header__user-menu',
    ORDERS_LIST: '.orders-list',
    ORDER_ITEM: '.order-card',
    ORDER_TITLE: '.order-card__title',
    ORDER_DESCRIPTION: '.order-card__description',
    ORDER_PRICE: '.order-card__price',
    ORDER_LINK: '.order-card__link',
    ORDER_ID_ATTR: 'data-order-id'
  },
  
  // URL
  URLS: {
    BASE: 'https://kwork.ru',
    LOGIN: 'https://kwork.ru/user/login',
    ORDERS: 'https://kwork.ru/projects',
    PROFILE: 'https://kwork.ru/user/profile'
  }
};

// Создаем директорию для сессий, если её нет
if (!fs.existsSync(CONFIG.SESSIONS_DIR)) {
  fs.mkdirSync(CONFIG.SESSIONS_DIR, { recursive: true });
}

// Глобальные переменные
let browser = null;
let page = null;
let isAuthenticated = false;
let currentProxy = null;
let lastSessionRefresh = 0;

// Загружаем время последнего обновления сессии
const loadLastRefreshTime = () => {
  try {
    if (fs.existsSync(CONFIG.SESSION.LAST_REFRESH_FILE)) {
      const data = JSON.parse(fs.readFileSync(CONFIG.SESSION.LAST_REFRESH_FILE, 'utf8'));
      lastSessionRefresh = data.lastRefresh || 0;
    }
  } catch (error) {
    console.error('Error loading last refresh time:', error);
  }
};

// Сохраняем время обновления сессии
const saveRefreshTime = () => {
  try {
    const dir = path.dirname(CONFIG.SESSION.LAST_REFRESH_FILE);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    lastSessionRefresh = Date.now();
    fs.writeFileSync(
      CONFIG.SESSION.LAST_REFRESH_FILE,
      JSON.stringify({ lastRefresh: lastSessionRefresh }),
      'utf8'
    );
  } catch (error) {
    console.error('Error saving refresh time:', error);
  }
};

// Проверяем, нужно ли обновить сессию
const isSessionExpired = () => {
  if (!lastSessionRefresh) return true;
  const now = Date.now();
  return (now - lastSessionRefresh) > (CONFIG.SESSION.TTL * 1000);
};

// Обновляем сессию
const refreshSession = async (username, password, pincode = '') => {
  try {
    console.log('Refreshing Kwork session...');
    
    // Закрываем текущую страницу и создаем новую
    if (page) {
      await page.close().catch(console.error);
    }
    
    const context = browser ? browser.contexts()[0] : null;
    if (!context) {
      throw new Error('Browser context not available');
    }
    
    page = await context.newPage();
    const refreshed = await authenticate(username, password, pincode);
    
    if (refreshed) {
      saveRefreshTime();
      console.log('Session refreshed successfully');
      return true;
    }
    
    return false;
  } catch (error) {
    console.error('Error refreshing session:', error);
    return false;
  }
};

/**
 * Инициализация браузера с прокси
 */
async function initBrowser(proxyConfig = null) {
  try {
    logWithTimestamp('Initializing browser...');
    
    // Закрываем существующий браузер, если он есть
    await closeBrowser();
    
    const launchOptions = {
      ...CONFIG.BROWSER,
      headless: true, // Всегда в headless режиме для стабильности
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-accelerated-2d-canvas',
        '--no-first-run',
        '--no-zygote',
        '--single-process',
        '--disable-gpu',
        '--disable-extensions',
        '--disable-software-rasterizer',
        '--disable-background-networking',
        '--disable-background-timer-throttling',
        '--disable-client-side-phishing-detection',
        '--disable-default-apps',
        '--disable-hang-monitor',
        '--disable-popup-blocking',
        '--disable-prompt-on-repost',
        '--disable-sync',
        '--metrics-recording-only',
        '--no-default-browser-check',
        '--safebrowsing-disable-auto-update',
        '--enable-automation',
        '--password-store=basic',
        '--use-mock-keychain',
        '--disable-blink-features=AutomationControlled'
      ],
      timeout: 60000 // 60 секунд таймаут на запуск браузера
    };

    // Настраиваем прокси, если он указан
    if (proxyConfig && proxyConfig.host && proxyConfig.port) {
      const proxyUrl = `${proxyConfig.protocol || 'http'}://${proxyConfig.host}:${proxyConfig.port}`;
      launchOptions.proxy = {
        server: proxyUrl,
        username: proxyConfig.auth?.username,
        password: proxyConfig.auth?.password
      };
      logWithTimestamp(`Using proxy: ${proxyUrl}`);
    }

    logWithTimestamp('Launching browser with options:', JSON.stringify({
      ...launchOptions,
      // Не логируем чувствительные данные
      proxy: launchOptions.proxy ? { 
        ...launchOptions.proxy, 
        password: launchOptions.proxy.password ? '***' : undefined 
      } : undefined
    }, null, 2));

    // Запускаем браузер
    browser = await chromium.launch(launchOptions);
    logWithTimestamp('Browser launched successfully');

    // Создаем контекст с настройками
    const context = await browser.newContext({
      viewport: { width: 1280, height: 1024 },
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
      ignoreHTTPSErrors: true,
      acceptDownloads: false,
      bypassCSP: true,
      javaScriptEnabled: true,
      offline: false,
      hasTouch: false,
      isMobile: false,
      locale: 'ru-RU',
      timezoneId: 'Europe/Moscow',
      permissions: ['geolocation'],
      extraHTTPHeaders: {
        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
        'Referer': 'https://kwork.ru/'
      }
    });

    // Устанавливаем таймауты
    context.setDefaultNavigationTimeout(60000); // 60 секунд
    context.setDefaultTimeout(30000); // 30 секунд

    // Включаем перехват запросов для оптимизации
    await context.route('**/*', route => {
      try {
        const request = route.request();
        const resourceType = request.resourceType();
        
        // Блокируем ненужные ресурсы для ускорения загрузки
        if (['image', 'stylesheet', 'font', 'media', 'other'].includes(resourceType)) {
          return route.abort();
        }
        
        // Продолжаем запрос
        return route.continue_();
      } catch (error) {
        logWithTimestamp(`Error in route handler: ${error.message}`);
        return route.abort();
      }
    });

    // Создаем новую страницу
    page = await context.newPage();
    logWithTimestamp('New page created successfully');

    // Устанавливаем дополнительные заголовки
    await page.setExtraHTTPHeaders({
      'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7'
    });

    // Эмулируем поведение реального пользователя
    await page.evaluateOnNewDocument(() => {
      // Убираем webdriver flag
      Object.defineProperty(navigator, 'webdriver', {
        get: () => false,
      });
      // Переопределяем languages
      Object.defineProperty(navigator, 'languages', {
        get: () => ['ru-RU', 'ru', 'en-US', 'en'],
      });
      // Переопределяем платформу
      Object.defineProperty(navigator, 'platform', {
        get: () => 'Win32',
      });
    });

    logWithTimestamp('Browser initialization completed');
    return { browser, page };
    
  } catch (error) {
    const errorMsg = `Failed to initialize browser: ${error.message}`;
    logWithTimestamp(errorMsg);
    logWithTimestamp('Error stack:', error.stack);
    
    // Пытаемся закрыть браузер в случае ошибки
    try {
      await closeBrowser();
    } catch (closeError) {
      logWithTimestamp('Error while closing browser after failure:', closeError.message);
    }
    
    throw new Error(errorMsg);
  }
}

/**
 * Закрытие браузера
 */
async function closeBrowser() {
  if (browser) {
    await browser.close();
    browser = null;
    page = null;
  }
}

/**
 * Аутентификация на Kwork
 */
async function authenticate(username, password, pincode = '') {
  try {
    logWithTimestamp('Starting authentication process...');
    
    // Проверяем валидность входных данных
    if (!username || !password) {
      throw new Error('Username and password are required');
    }

    // Проверяем, не истекла ли текущая сессия
    if (isAuthenticated && !isSessionExpired()) {
      logWithTimestamp('Using existing valid session');
      return true;
    }

    logWithTimestamp('Session expired or not authenticated, starting new authentication...');
    
    // Проверяем, инициализирована ли страница
    if (!page || page.isClosed()) {
      logWithTimestamp('Page is not initialized or closed, reinitializing...');
      await initBrowser();
    }

    // Переходим на страницу входа
    logWithTimestamp(`Navigating to login page: ${CONFIG.URLS.LOGIN}`);
    await page.goto(CONFIG.URLS.LOGIN, {
      waitUntil: 'domcontentloaded',
      timeout: CONFIG.TIMEOUTS.PAGE_LOAD
    });

    // Проверяем, что страница загрузилась корректно
    const pageTitle = await page.title();
    logWithTimestamp(`Page title: ${pageTitle}`);

    // Проверяем, не перенаправило ли нас уже на страницу профиля
    if (page.url().includes('kwork.ru/user/')) {
      logWithTimestamp('Already logged in, redirecting to profile page');
      isAuthenticated = true;
      saveRefreshTime();
      return true;
    }

    // Ожидаем появления формы входа
    logWithTimestamp('Waiting for login form...');
    try {
      await page.waitForSelector(CONFIG.SELECTORS.USERNAME_INPUT, { 
        state: 'visible', 
        timeout: 10000 
      });
    } catch (error) {
      const pageContent = await page.content();
      logWithTimestamp('Login form not found, page content:', pageContent);
      throw new Error('Login form not found on the page');
    }

    // Заполняем форму входа
    logWithTimestamp('Filling login form...');
    await page.fill(CONFIG.SELECTORS.USERNAME_INPUT, username);
    await page.fill(CONFIG.SELECTORS.PASSWORD_INPUT, password);
    
    // Делаем скриншот перед отправкой формы (для отладки)
    // await page.screenshot({ path: 'before-login.png' });
    
    // Нажимаем кнопку входа
    logWithTimestamp('Submitting login form...');
    const navigationPromise = page.waitForNavigation({ 
      waitUntil: 'networkidle',
      timeout: CONFIG.TIMEOUTS.NAVIGATION 
    });
    
    await page.click(CONFIG.SELECTORS.SUBMIT_BUTTON);
    await navigationPromise;

    // Проверяем наличие ошибки авторизации
    const errorElement = await page.$(CONFIG.SELECTORS.LOGIN_ERROR);
    if (errorElement) {
      const errorText = await errorElement.textContent();
      throw new Error(`Login failed: ${errorText.trim()}`);
    }

    // Проверяем, успешна ли аутентификация
    logWithTimestamp('Checking authentication status...');
    const isLoggedIn = await page.$(CONFIG.SELECTORS.PROFILE_MENU) !== null;
    
    if (isLoggedIn) {
      logWithTimestamp('Authentication successful');
      isAuthenticated = true;
      
      // Сохраняем куки для будущих сессий
      try {
        const cookies = await page.context().cookies();
        const sessionDir = path.dirname(path.join(CONFIG.SESSIONS_DIR, `${username}.json`));
        
        if (!fs.existsSync(sessionDir)) {
          fs.mkdirSync(sessionDir, { recursive: true });
        }
        
        const sessionPath = path.join(CONFIG.SESSIONS_DIR, `${username}.json`);
        fs.writeFileSync(sessionPath, JSON.stringify(cookies, null, 2));
        logWithTimestamp(`Session saved to ${sessionPath}`);
        
        saveRefreshTime();
        
        // Делаем скриншот после успешной авторизации (для отладки)
        // await page.screenshot({ path: 'after-login.png' });
        
        return true;
      } catch (saveError) {
        logWithTimestamp('Warning: Failed to save session:', saveError.message);
        // Продолжаем, даже если не удалось сохранить сессию
        return true;
      }
    }
    
    // Если дошли сюда, что-то пошло не так
    const currentUrl = page.url();
    const pageContent = await page.content();
    logWithTimestamp(`Authentication failed. Current URL: ${currentUrl}`);
    logWithTimestamp('Page content:', pageContent);
    
    throw new Error('Authentication failed: Unknown error');
    
  } catch (error) {
    const errorMessage = `Authentication error: ${error.message}`;
    logWithTimestamp(errorMessage);
    
    // Пытаемся сделать скриншот при ошибке
    try {
      await page.screenshot({ path: 'authentication-error.png' });
      logWithTimestamp('Screenshot saved to authentication-error.png');
    } catch (screenshotError) {
      logWithTimestamp('Failed to take screenshot on error:', screenshotError.message);
    }
    
    // Пробуем переинициализировать браузер для следующей попытки
    try {
      await closeBrowser();
      await initBrowser();
    } catch (browserError) {
      logWithTimestamp('Error while reinitializing browser after auth failure:', browserError.message);
    }
    
    isAuthenticated = false;
    throw error;
  }
}

/**
 * Получение списка заказов
 */
async function getOrders(params = {}) {
  const maxRetries = 3;
  let retryCount = 0;
  let lastError = null;
  
  // Параметры по умолчанию
  const defaultParams = {
    page: 1,
    category: 'all',
    type: 'all',
    budget: '',
    keywords: ''
  };
  
  // Объединяем переданные параметры с параметрами по умолчанию
  const requestParams = { ...defaultParams, ...params };
  
  logWithTimestamp(`Fetching orders with params: ${JSON.stringify(requestParams)}`);
  
  // Пытаемся получить заказы с возможностью повторных попыток
  while (retryCount < maxRetries) {
    try {
      // Формируем URL с параметрами запроса
      const url = new URL(CONFIG.URLS.ORDERS);
      Object.entries(requestParams).forEach(([key, value]) => {
        if (value) url.searchParams.append(key, value);
      });
      
      logWithTimestamp(`Navigating to orders page (attempt ${retryCount + 1}/${maxRetries}): ${url.toString()}`);
      
      // Переходим на страницу с заказами
      await page.goto(url.toString(), {
        waitUntil: 'domcontentloaded',
        timeout: CONFIG.TIMEOUTS.PAGE_LOAD
      });
      
      // Проверяем, не перенаправило ли нас на страницу входа
      if (page.url().includes('/user/login')) {
        throw new Error('Session expired, authentication required');
      }
      
      // Проверяем наличие капчи
      const captchaElement = await page.$(CONFIG.SELECTORS.CAPTCHA);
      if (captchaElement) {
        throw new Error('Captcha detected, manual intervention required');
      }
      
      // Ждем загрузки списка заказов или сообщения о пустом списке
      logWithTimestamp('Waiting for orders list to load...');
      try {
        // Сначала проверяем, есть ли сообщение об отсутствии заказов
        const noOrdersMessage = await page.$(CONFIG.SELECTORS.NO_ORDERS_MESSAGE);
        if (noOrdersMessage) {
          logWithTimestamp('No orders found matching the criteria');
          return { success: true, data: [], info: 'No orders found' };
        }
        
        // Если сообщения нет, ждем появления списка заказов
        await page.waitForSelector(CONFIG.SELECTORS.ORDERS_LIST, {
          state: 'attached',
          timeout: 15000 // 15 секунд на загрузку списка
        });
      } catch (waitError) {
        // Если не нашли ни списка, ни сообщения об отсутствии заказов
        logWithTimestamp('Orders list not found, checking page content...');
        const pageContent = await page.content();
        if (pageContent.includes('Список заказов пуст') || 
            pageContent.includes('По вашему запросу ничего не найдено')) {
          logWithTimestamp('No orders found (content check)');
          return { success: true, data: [], info: 'No orders found (content check)' };
        }
        throw waitError; // Пробрасываем ошибку дальше, если это не пустой список
      }
      
      // Делаем скриншот для отладки
      // await page.screenshot({ path: `orders-page-${Date.now()}.png` });
      
      logWithTimestamp('Extracting orders data...');
      
      // Извлекаем данные о заказах
      const orders = await page.$$eval(CONFIG.SELECTORS.ORDER_ITEM, (items, selectors) => {
        return items.map((item, index) => {
          try {
            return {
              id: item.getAttribute(selectors.ORDER_ID_ATTR) || `order-${index}`,
              title: item.querySelector(selectors.ORDER_TITLE)?.textContent?.trim() || 'No title',
              description: item.querySelector(selectors.ORDER_DESCRIPTION)?.textContent?.trim() || '',
              price: item.querySelector(selectors.ORDER_PRICE)?.textContent?.trim() || 'Не указана',
              url: item.querySelector(selectors.ORDER_LINK)?.href || '',
              timestamp: new Date().toISOString()
            };
          } catch (itemError) {
            console.error('Error processing order item:', itemError);
            return null;
          }
        }).filter(Boolean); // Удаляем null значения
      }, CONFIG.SELECTORS);
      
      logWithTimestamp(`Successfully extracted ${orders.length} orders`);
      
      // Если заказы найдены, возвращаем результат
      if (orders.length > 0) {
        return { 
          success: true, 
          data: orders,
          pagination: {
            page: parseInt(requestParams.page) || 1,
            hasMore: await page.$(CONFIG.SELECTORS.NEXT_PAGE) !== null
          }
        };
      } else {
        // Если заказов нет, но и ошибки не было, возвращаем пустой массив
        return { success: true, data: [], info: 'No orders found' };
      }
      
    } catch (error) {
      lastError = error;
      retryCount++;
      
      const errorMessage = `Attempt ${retryCount}/${maxRetries} failed: ${error.message}`;
      logWithTimestamp(errorMessage);
      
      // Если это последняя попытка, выходим из цикла
      if (retryCount >= maxRetries) break;
      
      // Если это ошибка аутентификации, не имеет смысла повторять
      if (error.message.includes('authentication') || 
          error.message.includes('session expired') ||
          error.message.includes('Captcha')) {
        logWithTimestamp('Authentication or captcha issue, aborting retries');
        break;
      }
      
      // Делаем паузу перед повторной попыткой (экспоненциальная задержка)
      const delay = Math.min(1000 * Math.pow(2, retryCount - 1), 10000);
      logWithTimestamp(`Retrying in ${delay}ms...`);
      await new Promise(resolve => setTimeout(resolve, delay));
      
      // Пробуем перезагрузить страницу перед следующей попыткой
      try {
        await page.reload({ waitUntil: 'domcontentloaded' });
      } catch (reloadError) {
        logWithTimestamp('Error during page reload:', reloadError.message);
      }
    }
  }
  
  // Если дошли сюда, значит все попытки исчерпаны
  const errorMessage = `Failed to get orders after ${maxRetries} attempts: ${lastError?.message || 'Unknown error'}`;
  logWithTimestamp(errorMessage);
  
  // Пытаемся сделать скриншот при ошибке
  try {
    await page.screenshot({ path: 'orders-error.png' });
    logWithTimestamp('Screenshot saved to orders-error.png');
  } catch (screenshotError) {
    logWithTimestamp('Failed to take screenshot on error:', screenshotError.message);
  }
  
  return { 
    success: false, 
    error: errorMessage,
    code: lastError?.code || 'ORDERS_FETCH_FAILED',
    retryCount
  };
}

/**
 * Обработка входящих команд
 */

// Initialize
loadLastRefreshTime();

// Handle incoming commands from stdin
process.stdin.setEncoding('utf8');

process.stdin.on('data', async (chunk) => {
    try {
        const inputData = chunk.toString().trim();
        if (!inputData) return;
        
        console.error('Raw input received:', inputData);
        
        let commandObj;
        try {
            commandObj = JSON.parse(inputData);
            console.error('Parsed command:', commandObj);
        } catch (parseError) {
            console.error('Failed to parse input as JSON:', parseError);
            sendErrorResponse('INVALID_JSON', 'Failed to parse input as JSON');
            return;
        }
        
        const { command, params = {} } = commandObj;
        let result;
        
        try {
            // Check session before executing command
            if (isSessionExpired() && command !== 'authenticate') {
                const username = process.env.KWORK_USERNAME;
                const password = process.env.KWORK_PASSWORD;
                const pincode = process.env.KWORK_PINCODE || '';
                
                if (username && password) {
                    await refreshSession(username, password, pincode);
                }
            }
            
            // Process command
            switch (command) {
                case 'init':
                    // Initialize with proxy if provided
                    await initBrowser(params.proxy);
                    result = { status: 'ready', session_created_at: Date.now() };
                    break;
                    
                case 'authenticate':
                    const { username, password, pincode } = params.credentials || {};
                    result = await authenticate(username, password, pincode);
                    break;
                    
                case 'getOrders':
                    result = await getOrders(params);
                    break;
                    
                case 'close':
                    await closeBrowser();
                    result = { success: true };
                    break;
                    
                default:
                    throw new Error(`Unknown command: ${command}`);
            }
            
            // Send success response
            sendSuccessResponse(result);
            
        } catch (error) {
            console.error(`Error executing command ${command}:`, error);
            sendErrorResponse('COMMAND_ERROR', error.message);
        }
    } catch (error) {
        console.error('Unexpected error:', error);
        sendErrorResponse('INTERNAL_ERROR', 'An unexpected error occurred');
    }
});

// Helper function to send success response
function sendSuccessResponse(data) {
    const response = { status: 'success', data };
    const responseStr = JSON.stringify(response) + '\n';
    process.stdout.write(responseStr, 'utf8', () => {
        if (process.stdout._handle && process.stdout._handle.setBlocking) {
            process.stdout._handle.setBlocking(true);
        }
        process.stdout.emit('drain');
    });
}

// Helper function to send error response
function sendErrorResponse(code, message) {
    const response = { status: 'error', error: { code, message } };
    const responseStr = JSON.stringify(response) + '\n';
    process.stdout.write(responseStr, 'utf8', () => {
        if (process.stdout._handle && process.stdout._handle.setBlocking) {
            process.stdout._handle.setBlocking(true);
        }
        process.stdout.emit('drain');
    });
}

// Handle process termination
process.on('SIGINT', async () => {
    console.error('Received SIGINT, closing browser...');
    await closeBrowser();
    process.exit(0);
});

// Error handlers
process.on('unhandledRejection', (error) => {
    console.error('Unhandled Rejection:', error);
    sendErrorResponse('UNHANDLED_REJECTION', error.message);
});

process.on('uncaughtException', (error) => {
    console.error('Uncaught Exception:', error);
    sendErrorResponse('UNCAUGHT_EXCEPTION', error.message);
});

// Start reading from stdin
process.stdin.resume();
console.error('📡 Kwork Node Bridge is ready and waiting for commands');;
