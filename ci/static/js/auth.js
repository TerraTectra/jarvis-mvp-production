// Authentication module
class Auth {
    constructor() {
        this.tokenKey = 'access_token';
        this.refreshTokenKey = 'refresh_token';
        this.apiBaseUrl = window.location.origin;
        this.init();
    }

    init() {
        // Check if we're on the login page
        if (window.location.pathname === '/login') {
            this.setupLoginForm();
        } else {
            this.setupAuthInterceptor();
            this.checkAuth();
        }
    }

    // Store tokens in localStorage
    setTokens(accessToken, refreshToken) {
        localStorage.setItem(this.tokenKey, accessToken);
        localStorage.setItem(this.refreshTokenKey, refreshToken);
    }

    // Remove tokens on logout
    clearTokens() {
        localStorage.removeItem(this.tokenKey);
        localStorage.removeItem(this.refreshTokenKey);
    }

    // Get access token
    getAccessToken() {
        return localStorage.getItem(this.tokenKey);
    }

    // Get refresh token
    getRefreshToken() {
        return localStorage.getItem(this.refreshTokenKey);
    }

    // Check if user is authenticated
    isAuthenticated() {
        return !!this.getAccessToken();
    }

    // Setup login form submission
    setupLoginForm() {
        const form = document.getElementById('loginForm');
        if (!form) return;

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            const errorElement = document.getElementById('error-message');
            const submitButton = document.getElementById('submit-button');
            const buttonText = submitButton.textContent;

            if (!username || !password) {
                errorElement.textContent = 'Пожалуйста, заполните все поля';
                return;
            }

            // Show loading state
            submitButton.disabled = true;
            submitButton.innerHTML = '<span class="loading-spinner"></span> Вход...';
            errorElement.textContent = '';

            try {
                const response = await fetch(`${this.apiBaseUrl}/ci/api/auth/token`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: new URLSearchParams({
                        username,
                        password,
                        grant_type: 'password'
                    })
                });

                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.detail || 'Неверное имя пользователя или пароль');
                }

                // Save tokens and redirect
                this.setTokens(data.access_token, data.refresh_token);
                window.location.href = '/ci/ui';
            } catch (error) {
                console.error('Login error:', error);
                errorElement.textContent = error.message || 'Произошла ошибка при входе';
                submitButton.disabled = false;
                submitButton.textContent = buttonText;
            }
        });
    }

    // Setup fetch interceptor to handle auth
    setupAuthInterceptor() {
        const originalFetch = window.fetch;
        
        window.fetch = async (url, options = {}) => {
            // Add auth header if we have a token
            const token = this.getAccessToken();
            if (token && !url.includes('/auth/token')) {
                options.headers = {
                    ...options.headers,
                    'Authorization': `Bearer ${token}`
                };
            }

            try {
                const response = await originalFetch(url, options);
                
                // If token expired, try to refresh it
                if (response.status === 401 && !url.includes('/auth/refresh')) {
                    return this.handleTokenRefresh()
                        .then(() => {
                            // Retry the original request with new token
                            const newToken = this.getAccessToken();
                            if (newToken) {
                                options.headers = {
                                    ...options.headers,
                                    'Authorization': `Bearer ${newToken}`
                                };
                                return originalFetch(url, options);
                            }
                            // If refresh failed, redirect to login
                            this.redirectToLogin();
                            return Promise.reject(new Error('Session expired'));
                        });
                }
                return response;
            } catch (error) {
                // If we can't reach the server, show error
                if (error.message === 'Failed to fetch') {
                    console.error('Network error:', error);
                    // You might want to show a notification to the user
                }
                throw error;
            }
        };
    }

    // Handle token refresh
    async handleTokenRefresh() {
        const refreshToken = this.getRefreshToken();
        if (!refreshToken) {
            this.redirectToLogin();
            return Promise.reject('No refresh token');
        }

        try {
            const response = await fetch(`${this.apiBaseUrl}/ci/api/auth/refresh`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: new URLSearchParams({
                    refresh_token: refreshToken,
                    grant_type: 'refresh_token'
                })
            });

            if (!response.ok) {
                throw new Error('Failed to refresh token');
            }

            const data = await response.json();
            this.setTokens(data.access_token, data.refresh_token);
            return data;
        } catch (error) {
            console.error('Token refresh failed:', error);
            this.clearTokens();
            this.redirectToLogin();
            throw error;
        }
    }

    // Redirect to login page
    redirectToLogin() {
        if (!window.location.pathname.includes('/login')) {
            window.location.href = '/login';
        }
    }

    // Check authentication status on page load
    checkAuth() {
        if (!this.isAuthenticated() && !window.location.pathname.includes('/login')) {
            this.redirectToLogin();
        }
    }
}

// Initialize auth when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.auth = new Auth();
});

// Logout function
function logout() {
    if (window.auth) {
        window.auth.clearTokens();
    }
    window.location.href = '/login';
}

// Make logout function available globally
window.logout = logout;
