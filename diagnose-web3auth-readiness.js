/**
 * RFC Web3Auth Integration Readiness Diagnostic
 * Created: 2025-01-28
 * Purpose: Check current auth system and database schema readiness
 */

const fs = require('fs');
const path = require('path');

// Check package.json for Web3Auth dependency
function checkWeb3AuthPackage() {
  console.log('🔍 Checking Web3Auth package installation...');

  const packagePath = path.join(__dirname, 'package.json');
  if (!fs.existsSync(packagePath)) {
    console.log('❌ package.json not found');
    return false;
  }

  const packageJson = JSON.parse(fs.readFileSync(packagePath, 'utf8'));
  const hasWeb3Auth = packageJson.dependencies && packageJson.dependencies['@web3auth/modal'];

  console.log(hasWeb3Auth ? '✅ @web3auth/modal is installed' : '❌ @web3auth/modal not installed');
  return hasWeb3Auth;
}

// Check .env for Web3Auth client ID
function checkWeb3AuthEnv() {
  console.log('\n🔍 Checking Web3Auth environment variables...');

  const envPath = path.join(__dirname, '.env');
  if (!fs.existsSync(envPath)) {
    console.log('❌ .env file not found');
    return false;
  }

  const envContent = fs.readFileSync(envPath, 'utf8');
  const hasClientId = envContent.includes('WEB3AUTH_CLIENT_ID=');
  const hasDevnetId = envContent.includes('WEB3AUTH_CLIENT_ID_DEVNET=');

  console.log(hasClientId ? '✅ WEB3AUTH_CLIENT_ID configured' : '❌ WEB3AUTH_CLIENT_ID missing');
  console.log(hasDevnetId ? '✅ WEB3AUTH_CLIENT_ID_DEVNET configured' : '❌ WEB3AUTH_CLIENT_ID_DEVNET missing');

  return hasClientId;
}

// Check database schema for Web3Auth fields
function checkDatabaseSchema() {
  console.log('\n🔍 Checking database schema for Web3Auth fields...');

  const flaskFile = path.join(__dirname, 'ietf_data_viewer_simple.py');
  if (!fs.existsSync(flaskFile)) {
    console.log('❌ Flask app file not found');
    return false;
  }

  const content = fs.readFileSync(flaskFile, 'utf8');

  const checks = [
    { field: 'web3authVerifierId', description: 'Web3Auth verifier ID field' },
    { field: 'typeOfLogin', description: 'Login type field (google/wallet/etc)' },
    { field: 'displayName', description: 'User display name field' },
    { field: 'displayNameSetAt', description: 'Display name timestamp' },
    { field: 'oauthName', description: 'OAuth provider name' },
    { field: 'evmAddress', description: 'EVM wallet address' },
    { field: 'solanaAddress', description: 'Solana wallet address' },
  ];

  let passed = 0;
  checks.forEach(check => {
    const hasField = content.includes(check.field);
    console.log(hasField ? `✅ ${check.description}` : `❌ ${check.description} missing`);
    if (hasField) passed++;
  });

  return passed === checks.length;
}

// Check for Web3Auth frontend files
function checkFrontendFiles() {
  console.log('\n🔍 Checking for Web3Auth frontend implementation...');

  const clientDir = path.join(__dirname, 'client');
  if (!fs.existsSync(clientDir)) {
    console.log('❌ client/ directory not found');
    return false;
  }

  const checks = [
    'lib/web3auth.ts',
    'components/UserDisplay.tsx',
    'components/WalletUserOnboarding.tsx',
    'hooks/useAuth.ts',
    'utils/wallet.ts',
  ];

  let found = 0;
  checks.forEach(file => {
    const filePath = path.join(clientDir, file);
    const exists = fs.existsSync(filePath);
    console.log(exists ? `✅ ${file} exists` : `❌ ${file} missing`);
    if (exists) found++;
  });

  return found > 0; // At least some files exist
}

// Check Flask routes for Web3Auth
function checkFlaskRoutes() {
  console.log('\n🔍 Checking Flask routes for Web3Auth endpoints...');

  const flaskFile = path.join(__dirname, 'ietf_data_viewer_simple.py');
  const content = fs.readFileSync(flaskFile, 'utf8');

  const routes = [
    '/api/auth/web3auth',
    '/api/user/display-name',
    '/api/user/me',
  ];

  let found = 0;
  routes.forEach(route => {
    const hasRoute = content.includes(route);
    console.log(hasRoute ? `✅ ${route} route exists` : `❌ ${route} route missing`);
    if (hasRoute) found++;
  });

  return found > 0;
}

// Main diagnostic function
function runDiagnostics() {
  console.log('🚀 RFC Web3Auth Integration Readiness Diagnostic');
  console.log('================================================\n');

  const results = {
    package: checkWeb3AuthPackage(),
    env: checkWeb3AuthEnv(),
    schema: checkDatabaseSchema(),
    frontend: checkFrontendFiles(),
    routes: checkFlaskRoutes(),
  };

  console.log('\n📊 SUMMARY');
  console.log('==========');

  const totalChecks = Object.keys(results).length;
  const passedChecks = Object.values(results).filter(Boolean).length;

  Object.entries(results).forEach(([check, passed]) => {
    console.log(`${passed ? '✅' : '❌'} ${check}: ${passed ? 'READY' : 'NEEDS WORK'}`);
  });

  console.log(`\n🎯 OVERALL READINESS: ${passedChecks}/${totalChecks} checks passed`);

  if (passedChecks === totalChecks) {
    console.log('🎉 System is ready for Web3Auth integration!');
  } else {
    console.log('⚠️  System needs work before Web3Auth integration.');
    console.log('\nNext steps:');
    if (!results.package) console.log('- Install @web3auth/modal package');
    if (!results.env) console.log('- Configure Web3Auth client IDs in .env');
    if (!results.schema) console.log('- Update database schema with Web3Auth fields');
    if (!results.frontend) console.log('- Implement frontend Web3Auth components');
    if (!results.routes) console.log('- Add backend Web3Auth API routes');
  }

  return results;
}

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { runDiagnostics };
}

// Run diagnostics if called directly
if (typeof require !== 'undefined' && require.main === module) {
  runDiagnostics();
}