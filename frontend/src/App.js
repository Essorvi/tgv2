import React, { useState, useEffect } from "react";
import "./App.css";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [stats, setStats] = useState({});
  const [users, setUsers] = useState([]);
  const [searches, setSearches] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState(null);
  const [giveUserId, setGiveUserId] = useState('');
  const [giveAttempts, setGiveAttempts] = useState('');

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    try {
      const [statsRes, usersRes, searchesRes] = await Promise.all([
        axios.get(`${API}/stats`),
        axios.get(`${API}/users`),
        axios.get(`${API}/searches`)
      ]);
      setStats(statsRes.data);
      setUsers(usersRes.data);
      setSearches(searchesRes.data);
    } catch (error) {
      console.error('Error loading dashboard data:', error);
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    
    setLoading(true);
    try {
      const response = await axios.post(`${API}/search?query=${encodeURIComponent(searchQuery)}`);
      setSearchResults(response.data);
    } catch (error) {
      console.error('Search error:', error);
      setSearchResults({ error: 'Search failed' });
    } finally {
      setLoading(false);
    }
  };

  const handleGiveAttempts = async () => {
    if (!giveUserId || !giveAttempts) return;
    
    setLoading(true);
    try {
      await axios.post(`${API}/give-attempts`, null, {
        params: {
          user_id: parseInt(giveUserId),
          attempts: parseInt(giveAttempts)
        }
      });
      alert('Attempts given successfully!');
      setGiveUserId('');
      setGiveAttempts('');
      loadDashboardData(); // Refresh data
    } catch (error) {
      console.error('Give attempts error:', error);
      alert('Failed to give attempts');
    } finally {
      setLoading(false);
    }
  };

  const formatResults = (results) => {
    if (!results) return '';
    if (results.error) return `Error: ${results.error}`;
    
    const data = results.data || {};
    const count = data.count || 0;
    
    if (count === 0) return 'No results found';
    
    let formatted = `Found ${count} results:\n\n`;
    
    if (data.items && Array.isArray(data.items)) {
      data.items.slice(0, 5).forEach((item, index) => {
        if (item.source && item.hits) {
          formatted += `${index + 1}. Database: ${item.source.database || 'N/A'}\n`;
          formatted += `   Collection: ${item.source.collection || 'N/A'}\n`;
          formatted += `   Hits: ${item.hits.hitsCount || item.hits.count || 0}\n\n`;
        }
      });
    }
    
    return formatted;
  };

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-blue-600 text-white shadow-lg">
        <div className="container mx-auto px-4 py-6">
          <h1 className="text-3xl font-bold">Usersbox Telegram Bot - Admin Panel</h1>
          <p className="text-blue-100 mt-2">Manage users, searches, and bot statistics</p>
        </div>
      </header>

      {/* Navigation */}
      <nav className="bg-white shadow-md">
        <div className="container mx-auto px-4">
          <div className="flex space-x-8">
            {['dashboard', 'users', 'searches', 'test', 'manage'].map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`py-4 px-2 border-b-2 font-medium text-sm ${
                  activeTab === tab
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                {tab.charAt(0).toUpperCase() + tab.slice(1)}
              </button>
            ))}
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-8">
        {/* Dashboard Tab */}
        {activeTab === 'dashboard' && (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold text-gray-800">Dashboard</h2>
            
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              <div className="bg-white p-6 rounded-lg shadow-md">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <div className="text-2xl">👥</div>
                  </div>
                  <div className="ml-4">
                    <p className="text-sm font-medium text-gray-500">Total Users</p>
                    <p className="text-2xl font-semibold text-gray-900">{stats.total_users || 0}</p>
                  </div>
                </div>
              </div>

              <div className="bg-white p-6 rounded-lg shadow-md">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <div className="text-2xl">🔍</div>
                  </div>
                  <div className="ml-4">
                    <p className="text-sm font-medium text-gray-500">Total Searches</p>
                    <p className="text-2xl font-semibold text-gray-900">{stats.total_searches || 0}</p>
                  </div>
                </div>
              </div>

              <div className="bg-white p-6 rounded-lg shadow-md">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <div className="text-2xl">🔗</div>
                  </div>
                  <div className="ml-4">
                    <p className="text-sm font-medium text-gray-500">Total Referrals</p>
                    <p className="text-2xl font-semibold text-gray-900">{stats.total_referrals || 0}</p>
                  </div>
                </div>
              </div>

              <div className="bg-white p-6 rounded-lg shadow-md">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <div className="text-2xl">✅</div>
                  </div>
                  <div className="ml-4">
                    <p className="text-sm font-medium text-gray-500">Success Rate</p>
                    <p className="text-2xl font-semibold text-gray-900">{stats.success_rate?.toFixed(1) || 0}%</p>
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-white p-6 rounded-lg shadow-md">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Quick Actions</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <button
                  onClick={() => setActiveTab('users')}
                  className="bg-blue-500 hover:bg-blue-600 text-white font-medium py-2 px-4 rounded-md"
                >
                  View Users
                </button>
                <button
                  onClick={() => setActiveTab('searches')}
                  className="bg-green-500 hover:bg-green-600 text-white font-medium py-2 px-4 rounded-md"
                >
                  View Searches
                </button>
                <button
                  onClick={() => setActiveTab('test')}
                  className="bg-purple-500 hover:bg-purple-600 text-white font-medium py-2 px-4 rounded-md"
                >
                  Test Search
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Users Tab */}
        {activeTab === 'users' && (
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <h2 className="text-2xl font-bold text-gray-800">Users</h2>
              <button
                onClick={loadDashboardData}
                className="bg-blue-500 hover:bg-blue-600 text-white font-medium py-2 px-4 rounded-md"
              >
                Refresh
              </button>
            </div>

            <div className="bg-white shadow-md rounded-lg overflow-hidden">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      User
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Attempts
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Referrals
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Joined
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {users.map((user) => (
                    <tr key={user.telegram_id}>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div>
                          <div className="text-sm font-medium text-gray-900">
                            {user.first_name} {user.last_name}
                          </div>
                          <div className="text-sm text-gray-500">
                            @{user.username} ({user.telegram_id})
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {user.attempts_remaining}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {user.total_referrals}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                          user.is_admin 
                            ? 'bg-red-100 text-red-800' 
                            : 'bg-green-100 text-green-800'
                        }`}>
                          {user.is_admin ? 'Admin' : 'User'}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {new Date(user.created_at).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Searches Tab */}
        {activeTab === 'searches' && (
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <h2 className="text-2xl font-bold text-gray-800">Recent Searches</h2>
              <button
                onClick={loadDashboardData}
                className="bg-blue-500 hover:bg-blue-600 text-white font-medium py-2 px-4 rounded-md"
              >
                Refresh
              </button>
            </div>

            <div className="bg-white shadow-md rounded-lg overflow-hidden">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      User ID
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Query
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Time
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {searches.map((search, index) => (
                    <tr key={index}>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {search.user_id}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {search.query}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                          search.success 
                            ? 'bg-green-100 text-green-800' 
                            : 'bg-red-100 text-red-800'
                        }`}>
                          {search.success ? 'Success' : 'Failed'}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {new Date(search.timestamp).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Test Search Tab */}
        {activeTab === 'test' && (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold text-gray-800">Test Search</h2>

            <div className="bg-white p-6 rounded-lg shadow-md">
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Search Query
                  </label>
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Enter search query (phone, email, name, etc.)"
                  />
                </div>
                <button
                  onClick={handleSearch}
                  disabled={loading || !searchQuery.trim()}
                  className="bg-blue-500 hover:bg-blue-600 disabled:bg-gray-400 text-white font-medium py-2 px-4 rounded-md"
                >
                  {loading ? 'Searching...' : 'Search'}
                </button>
              </div>

              {searchResults && (
                <div className="mt-6">
                  <h3 className="text-lg font-medium text-gray-900 mb-3">Results:</h3>
                  <pre className="bg-gray-100 p-4 rounded-md text-sm overflow-auto max-h-96">
                    {formatResults(searchResults)}
                  </pre>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Manage Tab */}
        {activeTab === 'manage' && (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold text-gray-800">User Management</h2>

            <div className="bg-white p-6 rounded-lg shadow-md">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Give Attempts</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    User ID
                  </label>
                  <input
                    type="text"
                    value={giveUserId}
                    onChange={(e) => setGiveUserId(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Telegram User ID"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Attempts
                  </label>
                  <input
                    type="number"
                    value={giveAttempts}
                    onChange={(e) => setGiveAttempts(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Number of attempts"
                    min="1"
                  />
                </div>
                <div className="flex items-end">
                  <button
                    onClick={handleGiveAttempts}
                    disabled={loading || !giveUserId || !giveAttempts}
                    className="w-full bg-green-500 hover:bg-green-600 disabled:bg-gray-400 text-white font-medium py-2 px-4 rounded-md"
                  >
                    {loading ? 'Processing...' : 'Give Attempts'}
                  </button>
                </div>
              </div>
            </div>

            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
              <h4 className="text-sm font-medium text-yellow-800">Instructions:</h4>
              <ul className="mt-2 text-sm text-yellow-700 list-disc list-inside space-y-1">
                <li>Enter the Telegram user ID (visible in the users table above)</li>
                <li>Specify the number of attempts to give to the user</li>
                <li>The user will be notified in Telegram about the new attempts</li>
                <li>Use this feature responsibly to help users with legitimate needs</li>
              </ul>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;