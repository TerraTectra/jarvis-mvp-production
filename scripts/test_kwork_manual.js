const Kwork = require('kwork-api');
require('dotenv').config();

const kwork = new Kwork({
  login: process.env.KWORK_USERNAME,
  password: process.env.KWORK_PASSWORD,
  pincode: process.env.KWORK_PINCODE || '',
  debug: true
});

async function test() {
  try {
    console.log('Trying to get profile...');
    const profile = await kwork.getProfile();
    console.log('Profile:', JSON.stringify(profile, null, 2));
    
    console.log('\nTrying to get orders...');
    const orders = await kwork.getOrders({ page: 1 });
    console.log('Orders:', JSON.stringify(orders, null, 2));
    
  } catch (error) {
    console.error('Error:', error);
    if (error.response) {
      console.error('Response data:', error.response.data);
      console.error('Response status:', error.response.status);
      console.error('Response headers:', error.response.headers);
    }
  }
}

test();
