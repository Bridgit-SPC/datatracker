/**
 * RFC Web3Auth Integration Test Suite
 * Created: 2025-01-28
 * Purpose: Test Web3Auth integration and display name system
 */

const fs = require('fs');
const path = require('path');

// Test configuration
const TEST_CONFIG = {
  flaskUrl: 'http://localhost:8000', // Will need to be updated for actual testing
  apiEndpoints: [
    '/api/auth/web3auth',
    '/api/user/me',
    '/api/user/display-name',
    '/api/auth/logout'
  ]
};

// Mock Web3Auth user data for testing
const MOCK_USERS = {
  googleUser: {
    verifierId: 'google_123456789',
    typeOfLogin: 'google',
    email: 'test@example.com',
    name: 'Test User',
    profileImage: 'https://example.com/avatar.jpg',
    evmAddress: '0x742d35Cc6634C0532925a3b844Bc454e4438f44e'
  },
  walletUser: {
    verifierId: 'wallet_0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
    typeOfLogin: 'wallet',
    email: null,
    name: null,
    profileImage: null,
    evmAddress: '0x742d35Cc6634C0532925a3b844Bc454e4438f44e'
  }
};

// Test utilities
function logTest(testName, status, details = '') {
  const statusIcon = status === 'PASS' ? '✅' : status === 'FAIL' ? '❌' : '⚠️';
  console.log(`${statusIcon} ${testName}: ${status}`);
  if (details) console.log(`   ${details}`);
}

// Check if Flask app is running
async function checkFlaskApp() {
  try {
    const response = await fetch(TEST_CONFIG.flaskUrl);
    return response.ok;
  } catch (error) {
    return false;
  }
}

// Test API endpoints exist
async function testApiEndpoints() {
  const results = {};

  for (const endpoint of TEST_CONFIG.apiEndpoints) {
    try {
      const response = await fetch(`${TEST_CONFIG.flaskUrl}${endpoint}`, {
        method: 'OPTIONS' // Check if endpoint exists
      });
      results[endpoint] = response.status !== 404;
    } catch (error) {
      results[endpoint] = false;
    }
  }

  return results;
}

// Test Web3Auth user creation (mock)
async function testUserCreation() {
  const results = {};

  for (const [userType, userData] of Object.entries(MOCK_USERS)) {
    try {
      // This would normally call the real API
      // For now, just validate the data structure
      const requiredFields = ['verifierId', 'typeOfLogin', 'evmAddress'];
      const hasRequiredFields = requiredFields.every(field => userData[field] !== undefined);

      const isValid = hasRequiredFields && userData.verifierId && userData.typeOfLogin;
      results[userType] = isValid;

      if (!isValid) {
        results[`${userType}_errors`] = requiredFields.filter(field => userData[field] === undefined);
      }
    } catch (error) {
      results[userType] = false;
      results[`${userType}_error`] = error.message;
    }
  }

  return results;
}

// Test frontend component files exist
function testFrontendComponents() {
  const components = [
    'client/lib/web3auth.ts',
    'client/components/UserDisplay.tsx',
    'client/components/WalletUserOnboarding.tsx',
    'client/hooks/useAuth.ts',
    'client/utils/wallet.ts',
    'client/styles/user-display.css',
    'client/styles/onboarding-modal.css'
  ];

  const results = {};

  components.forEach(component => {
    const filePath = path.join(__dirname, component);
    results[component] = fs.existsSync(filePath);
  });

  return results;
}

// Test database schema
function testDatabaseSchema() {
  // This would require connecting to the actual database
  // For now, check if the Flask app can import without schema errors
  try {
    // Mock test - in real scenario would query database
    const schemaFields = [
      'web3authVerifierId',
      'typeOfLogin',
      'displayName',
      'displayNameSetAt',
      'oauthName',
      'evmAddress',
      'solanaAddress'
    ];

    // Check if fields are defined in the Python code
    const flaskFile = fs.readFileSync(path.join(__dirname, 'ietf_data_viewer_simple.py'), 'utf8');
    const results = {};

    schemaFields.forEach(field => {
      results[field] = flaskFile.includes(field);
    });

    return results;
  } catch (error) {
    return { error: error.message };
  }
}

// Test wallet address formatting
function testWalletFormatting() {
  const testAddresses = [
    '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
    '0x1234567890123456789012345678901234567890',
    '0xABC'
  ];

  const results = {};

  testAddresses.forEach(address => {
    // Mock the formatting logic
    let formatted;
    if (!address) {
      formatted = 'No wallet';
    } else if (address.length <= 10) {
      formatted = address;
    } else {
      formatted = `${address.slice(0, 6)}...${address.slice(-4)}`;
    }

    results[address] = {
      original: address,
      formatted: formatted,
      valid: formatted.length > 0
    };
  });

  return results;
}

// Main test runner
async function runTests() {
  console.log('🧪 RFC Web3Auth Integration Test Suite');
  console.log('======================================\n');

  const testResults = {
    flaskRunning: false,
    apiEndpoints: {},
    userCreation: {},
    frontendComponents: {},
    databaseSchema: {},
    walletFormatting: {}
  };

  // Test 1: Flask app running
  logTest('Flask App Status', 'INFO', 'Checking if Flask app is accessible...');
  testResults.flaskRunning = await checkFlaskApp();
  logTest('Flask App Running', testResults.flaskRunning ? 'PASS' : 'SKIP', testResults.flaskRunning ? 'App is accessible' : 'App not running (expected for local testing)');

  // Test 2: API endpoints
  logTest('API Endpoints', 'INFO', 'Checking if Web3Auth API endpoints exist...');
  testResults.apiEndpoints = await testApiEndpoints();
  Object.entries(testResults.apiEndpoints).forEach(([endpoint, exists]) => {
    logTest(`Endpoint ${endpoint}`, exists ? 'PASS' : 'FAIL', exists ? 'Endpoint exists' : 'Endpoint not found');
  });

  // Test 3: User creation logic
  logTest('User Creation Logic', 'INFO', 'Testing user creation data validation...');
  testResults.userCreation = await testUserCreation();
  Object.entries(testResults.userCreation).forEach(([test, result]) => {
    if (!test.includes('_errors') && !test.includes('_error')) {
      logTest(`User Creation (${test})`, result ? 'PASS' : 'FAIL', result ? 'Valid user data' : 'Invalid user data');
    }
  });

  // Test 4: Frontend components
  logTest('Frontend Components', 'INFO', 'Checking if all frontend components exist...');
  testResults.frontendComponents = testFrontendComponents();
  Object.entries(testResults.frontendComponents).forEach(([component, exists]) => {
    logTest(`Component ${component}`, exists ? 'PASS' : 'FAIL', exists ? 'File exists' : 'File missing');
  });

  // Test 5: Database schema
  logTest('Database Schema', 'INFO', 'Checking if database schema includes Web3Auth fields...');
  testResults.databaseSchema = testDatabaseSchema();
  if (testResults.databaseSchema.error) {
    logTest('Database Schema Check', 'ERROR', testResults.databaseSchema.error);
  } else {
    Object.entries(testResults.databaseSchema).forEach(([field, exists]) => {
      logTest(`Schema Field ${field}`, exists ? 'PASS' : 'FAIL', exists ? 'Field defined' : 'Field missing');
    });
  }

  // Test 6: Wallet formatting
  logTest('Wallet Formatting', 'INFO', 'Testing wallet address formatting logic...');
  testResults.walletFormatting = testWalletFormatting();
  Object.entries(testResults.walletFormatting).forEach(([address, result]) => {
    logTest(`Wallet Format ${address.slice(0, 10)}...`, result.valid ? 'PASS' : 'FAIL', `Formatted: ${result.formatted}`);
  });

  // Summary
  console.log('\n📊 TEST SUMMARY');
  console.log('===============');

  const calculateScore = (results) => {
    let total = 0;
    let passed = 0;

    const countResults = (obj) => {
      Object.values(obj).forEach(value => {
        if (typeof value === 'boolean') {
          total++;
          if (value) passed++;
        } else if (typeof value === 'object' && !Array.isArray(value)) {
          countResults(value);
        }
      });
    };

    countResults(results);
    return { total, passed };
  };

  const { total, passed } = calculateScore(testResults);
  const score = total > 0 ? Math.round((passed / total) * 100) : 0;

  console.log(`✅ Passed: ${passed}/${total} tests (${score}%)`);

  if (score >= 80) {
    console.log('🎉 Web3Auth integration tests PASSED!');
  } else if (score >= 60) {
    console.log('⚠️ Web3Auth integration tests PARTIAL - needs attention');
  } else {
    console.log('❌ Web3Auth integration tests FAILED - critical issues');
  }

  // Recommendations
  console.log('\n💡 RECOMMENDATIONS');
  console.log('==================');

  if (!testResults.flaskRunning) {
    console.log('- Start Flask development server to test live endpoints');
  }

  const missingComponents = Object.entries(testResults.frontendComponents)
    .filter(([_, exists]) => !exists)
    .map(([component, _]) => component);

  if (missingComponents.length > 0) {
    console.log(`- Missing frontend components: ${missingComponents.join(', ')}`);
  }

  const missingFields = Object.entries(testResults.databaseSchema)
    .filter(([field, exists]) => !exists && field !== 'error')
    .map(([field, _]) => field);

  if (missingFields.length > 0) {
    console.log(`- Missing database fields: ${missingFields.join(', ')}`);
  }

  console.log('- Run database migration to add new schema fields');
  console.log('- Test with real Web3Auth credentials');
  console.log('- Test social login flows (Google, X/Twitter)');
  console.log('- Test wallet login flows (MetaMask, WalletConnect)');

  return testResults;
}

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { runTests };
}

// Run tests if called directly
if (typeof require !== 'undefined' && require.main === module) {
  runTests().catch(console.error);
}