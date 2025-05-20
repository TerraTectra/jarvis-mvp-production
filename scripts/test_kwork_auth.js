const Kwork = require('kwork-api');
require('dotenv').config();

console.log('Starting Kwork API test...');
console.log('Environment variables loaded:', {
  KWORK_USERNAME: process.env.KWORK_USERNAME ? '***' : 'NOT SET',
  KWORK_PASSWORD: process.env.KWORK_PASSWORD ? '***' : 'NOT SET',
  KWORK_PINCODE: process.env.KWORK_PINCODE || 'NOT SET'
});

const kwork = new Kwork({
  login: process.env.KWORK_USERNAME,
  password: process.env.KWORK_PASSWORD,
  pincode: process.env.KWORK_PINCODE || '',
  debug: true
});

async function testAuth() {
  try {
    console.log('Trying to get profile...');
    const profile = await kwork.getProfile();
    console.log('Profile:', JSON.stringify(profile, null, 2));
    return true;
  } catch (error) {
    console.error('Auth Error:', {
      message: error.message,
      response: error.response ? {
        status: error.response.status,
        statusText: error.response.statusText,
        headers: error.response.headers,
        data: error.response.data
      } : 'No response',
      stack: error.stack
    });
    return false;
  }
}

async function main() {
  const isAuthenticated = await testAuth();
  if (!isAuthenticated) {
    console.log('Authentication failed. Please check your credentials and try again.');
    process.exit(1);
  }
}

main();
