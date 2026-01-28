'use client';

import { useState, useEffect, useCallback } from 'react';
import dynamic from 'next/dynamic';
import { useAppStore } from '@/lib/store';
import Sidebar from '@/components/Sidebar';
import NodeDetails from '@/components/NodeDetails';
import ImageUpload from '@/components/ImageUpload';
import type { GraphNode } from '@/types';
import {
  Users,
  Image,
  MapPin,
  Hash,
  RefreshCw,
  Layers,
  Box,
  Instagram,
  Loader2,
} from 'lucide-react';
import { personsApi, postsApi, graphApi, instagramApi } from '@/lib/api';
import { formatDate, formatNumber, getNodeTypeColor } from '@/lib/utils';

// Dynamically import GraphVisualization to avoid SSR issues
const GraphVisualization = dynamic(
  () => import('@/components/GraphVisualization'),
  { ssr: false, loading: () => <div className="flex items-center justify-center h-full"><Loader2 className="w-8 h-8 animate-spin" /></div> }
);

export default function Home() {
  const {
    graphData,
    persons,
    posts,
    stats,
    selectedNode,
    isLoading,
    graphMode,
    setSelectedNode,
    setGraphMode,
    fetchGraphData,
    fetchPersons,
    fetchPosts,
    fetchStats,
    fetchPersonNetwork,
  } = useAppStore();

  const [currentView, setCurrentView] = useState('graph');
  const [graphDimensions, setGraphDimensions] = useState({ width: 800, height: 600 });

  // Instagram import state
  const [importUsername, setImportUsername] = useState('');
  const [importMaxPosts, setImportMaxPosts] = useState(50);
  const [importing, setImporting] = useState(false);
  const [importStatus, setImportStatus] = useState<any>(null);

  // Initial data load
  useEffect(() => {
    fetchStats();
    fetchGraphData();
    fetchPersons();
    fetchPosts();
  }, [fetchStats, fetchGraphData, fetchPersons, fetchPosts]);

  // Update graph dimensions on window resize
  useEffect(() => {
    const updateDimensions = () => {
      const container = document.getElementById('graph-container');
      if (container) {
        setGraphDimensions({
          width: container.clientWidth,
          height: container.clientHeight,
        });
      }
    };

    updateDimensions();
    window.addEventListener('resize', updateDimensions);
    return () => window.removeEventListener('resize', updateDimensions);
  }, [currentView]);

  const handleNodeClick = useCallback((node: GraphNode) => {
    setSelectedNode(node);
  }, [setSelectedNode]);

  const handleExploreNetwork = useCallback((nodeId: string) => {
    fetchPersonNetwork(nodeId, 2);
    setSelectedNode(null);
  }, [fetchPersonNetwork, setSelectedNode]);

  const handleInstagramImport = async () => {
    if (!importUsername.trim()) return;

    setImporting(true);
    setImportStatus(null);

    try {
      const result = await instagramApi.importPosts(importUsername, importMaxPosts);
      setImportStatus({ ...result, status: 'started' });

      // Poll for status
      const pollStatus = async () => {
        const status = await instagramApi.getImportStatus(result.job_id);
        setImportStatus(status);

        if (status.status === 'running') {
          setTimeout(pollStatus, 2000);
        } else {
          setImporting(false);
          // Refresh data
          fetchGraphData();
          fetchPersons();
          fetchPosts();
          fetchStats();
        }
      };

      setTimeout(pollStatus, 2000);
    } catch (error: any) {
      setImportStatus({ status: 'failed', error: error.message });
      setImporting(false);
    }
  };

  const renderContent = () => {
    switch (currentView) {
      case 'graph':
        return (
          <div className="flex-1 relative" id="graph-container">
            {/* Toolbar */}
            <div className="absolute top-4 left-4 z-10 flex gap-2">
              <button
                onClick={() => fetchGraphData()}
                className="p-2 bg-white rounded-lg shadow hover:bg-gray-50"
                title="Refresh Graph"
              >
                <RefreshCw className={`w-5 h-5 ${isLoading ? 'animate-spin' : ''}`} />
              </button>
              <button
                onClick={() => setGraphMode(graphMode === '2d' ? '3d' : '2d')}
                className="p-2 bg-white rounded-lg shadow hover:bg-gray-50"
                title={`Switch to ${graphMode === '2d' ? '3D' : '2D'}`}
              >
                {graphMode === '2d' ? <Box className="w-5 h-5" /> : <Layers className="w-5 h-5" />}
              </button>
            </div>

            {/* Legend */}
            <div className="absolute top-4 right-4 z-10 bg-white p-3 rounded-lg shadow">
              <h4 className="text-sm font-medium text-gray-500 mb-2">Legend</h4>
              <div className="space-y-1 text-sm">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-red-500" />
                  <span>Person</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-blue-500" />
                  <span>Post</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-green-500" />
                  <span>Location</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-purple-500" />
                  <span>Account</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-orange-500" />
                  <span>Hashtag</span>
                </div>
              </div>
            </div>

            {/* Graph */}
            {graphData && graphData.nodes.length > 0 ? (
              <GraphVisualization
                data={graphData}
                mode={graphMode}
                onNodeClick={handleNodeClick}
                width={graphDimensions.width}
                height={graphDimensions.height}
              />
            ) : (
              <div className="flex items-center justify-center h-full text-gray-500">
                {isLoading ? (
                  <Loader2 className="w-8 h-8 animate-spin" />
                ) : (
                  <div className="text-center">
                    <p className="mb-2">No data to display</p>
                    <p className="text-sm">Upload images or import from Instagram to get started</p>
                  </div>
                )}
              </div>
            )}

            {/* Node Details Panel */}
            {selectedNode && (
              <NodeDetails
                node={selectedNode}
                onClose={() => setSelectedNode(null)}
                onExploreNetwork={handleExploreNetwork}
              />
            )}
          </div>
        );

      case 'persons':
        return (
          <div className="p-6">
            <h2 className="text-2xl font-bold text-gray-900 mb-6">Persons</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {persons.map((person) => (
                <div
                  key={person.id}
                  className="bg-white rounded-lg shadow p-4 card-hover cursor-pointer"
                  onClick={() =>
                    handleNodeClick({
                      id: person.id,
                      label: person.name,
                      type: 'Person',
                      properties: person as any,
                    })
                  }
                >
                  <div className="flex items-center gap-3">
                    {person.profile_image ? (
                      <img
                        src={person.profile_image}
                        alt={person.name}
                        className="w-12 h-12 rounded-full object-cover"
                      />
                    ) : (
                      <div className="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center">
                        <Users className="w-6 h-6 text-red-600" />
                      </div>
                    )}
                    <div>
                      <h3 className="font-medium text-gray-900">{person.name}</h3>
                      <p className="text-sm text-gray-500">
                        {person.post_count} appearances
                      </p>
                    </div>
                  </div>
                </div>
              ))}
              {persons.length === 0 && (
                <p className="text-gray-500 col-span-full text-center py-8">
                  No persons found. Upload images to detect faces.
                </p>
              )}
            </div>
          </div>
        );

      case 'posts':
        return (
          <div className="p-6">
            <h2 className="text-2xl font-bold text-gray-900 mb-6">Posts</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {posts.map((post) => (
                <div
                  key={post.id}
                  className="bg-white rounded-lg shadow overflow-hidden card-hover"
                >
                  {post.image_urls[0] && (
                    <img
                      src={post.image_urls[0]}
                      alt={post.shortcode}
                      className="w-full h-48 object-cover"
                    />
                  )}
                  <div className="p-4">
                    <p className="text-sm text-gray-500 mb-2">
                      {post.caption?.slice(0, 100)}
                      {(post.caption?.length || 0) > 100 && '...'}
                    </p>
                    <div className="flex justify-between text-sm">
                      <span>{formatNumber(post.likes)} likes</span>
                      <span>{post.faces_detected} faces</span>
                    </div>
                    {post.posted_at && (
                      <p className="text-xs text-gray-400 mt-2">
                        {formatDate(post.posted_at)}
                      </p>
                    )}
                  </div>
                </div>
              ))}
              {posts.length === 0 && (
                <p className="text-gray-500 col-span-full text-center py-8">
                  No posts found. Upload images to get started.
                </p>
              )}
            </div>
          </div>
        );

      case 'upload':
        return (
          <div className="p-6">
            <div className="max-w-4xl mx-auto">
              <div className="flex gap-4 mb-6">
                <button
                  onClick={() => setCurrentView('upload-post')}
                  className="flex-1 p-4 bg-white rounded-lg shadow hover:shadow-md transition-shadow text-center"
                >
                  <Image className="w-8 h-8 mx-auto mb-2 text-blue-600" />
                  <h3 className="font-medium">Upload Post</h3>
                  <p className="text-sm text-gray-500">Analyze image for faces</p>
                </button>
                <button
                  onClick={() => setCurrentView('upload-person')}
                  className="flex-1 p-4 bg-white rounded-lg shadow hover:shadow-md transition-shadow text-center"
                >
                  <Users className="w-8 h-8 mx-auto mb-2 text-red-600" />
                  <h3 className="font-medium">Add Person</h3>
                  <p className="text-sm text-gray-500">Register a new face</p>
                </button>
              </div>
            </div>
          </div>
        );

      case 'upload-post':
        return (
          <ImageUpload
            mode="post"
            onSuccess={() => {
              fetchGraphData();
              fetchPosts();
              fetchStats();
            }}
          />
        );

      case 'upload-person':
        return (
          <ImageUpload
            mode="person"
            onSuccess={() => {
              fetchPersons();
              fetchStats();
            }}
          />
        );

      case 'instagram':
        return (
          <div className="p-6 max-w-2xl mx-auto">
            <h2 className="text-2xl font-bold text-gray-900 mb-6">
              <Instagram className="inline w-8 h-8 mr-2" />
              Instagram Import
            </h2>

            <div className="bg-white rounded-lg shadow p-6">
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Username
                  </label>
                  <input
                    type="text"
                    value={importUsername}
                    onChange={(e) => setImportUsername(e.target.value)}
                    placeholder="Enter Instagram username"
                    className="w-full p-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Max Posts
                  </label>
                  <input
                    type="number"
                    value={importMaxPosts}
                    onChange={(e) => setImportMaxPosts(parseInt(e.target.value))}
                    min={1}
                    max={100}
                    className="w-full p-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500"
                  />
                </div>

                <button
                  onClick={handleInstagramImport}
                  disabled={importing || !importUsername.trim()}
                  className="w-full py-3 px-4 bg-gradient-to-r from-purple-600 to-pink-600 text-white rounded-lg hover:from-purple-700 hover:to-pink-700 disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {importing ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      Importing...
                    </>
                  ) : (
                    <>
                      <Instagram className="w-5 h-5" />
                      Start Import
                    </>
                  )}
                </button>
              </div>

              {/* Import status */}
              {importStatus && (
                <div
                  className={`mt-4 p-4 rounded-lg ${
                    importStatus.status === 'completed'
                      ? 'bg-green-50 border border-green-200'
                      : importStatus.status === 'failed'
                      ? 'bg-red-50 border border-red-200'
                      : 'bg-blue-50 border border-blue-200'
                  }`}
                >
                  <h4 className="font-medium mb-2">
                    Status: {importStatus.status}
                  </h4>
                  {importStatus.processed_posts !== undefined && (
                    <p className="text-sm">
                      Processed: {importStatus.processed_posts} / {importStatus.total_posts || '?'} posts
                    </p>
                  )}
                  {importStatus.faces_detected !== undefined && (
                    <p className="text-sm">
                      Faces detected: {importStatus.faces_detected}
                    </p>
                  )}
                  {importStatus.errors?.length > 0 && (
                    <div className="mt-2">
                      <p className="text-sm font-medium text-red-600">Errors:</p>
                      <ul className="text-sm text-red-500 list-disc list-inside">
                        {importStatus.errors.slice(0, 5).map((err: string, idx: number) => (
                          <li key={idx}>{err}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="mt-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
              <h4 className="font-medium text-yellow-800 mb-2">Note</h4>
              <p className="text-sm text-yellow-700">
                Instagram import requires public profiles or authentication.
                For private profiles, you need to configure Instagram credentials
                in the backend environment variables.
              </p>
            </div>
          </div>
        );

      case 'stats':
        return (
          <div className="p-6">
            <h2 className="text-2xl font-bold text-gray-900 mb-6">Statistics</h2>
            {stats ? (
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
                <div className="bg-white rounded-lg shadow p-4 text-center">
                  <Users className="w-8 h-8 mx-auto mb-2 text-red-500" />
                  <div className="text-2xl font-bold">{stats.total_persons}</div>
                  <div className="text-sm text-gray-500">Persons</div>
                </div>
                <div className="bg-white rounded-lg shadow p-4 text-center">
                  <Image className="w-8 h-8 mx-auto mb-2 text-blue-500" />
                  <div className="text-2xl font-bold">{stats.total_posts}</div>
                  <div className="text-sm text-gray-500">Posts</div>
                </div>
                <div className="bg-white rounded-lg shadow p-4 text-center">
                  <MapPin className="w-8 h-8 mx-auto mb-2 text-green-500" />
                  <div className="text-2xl font-bold">{stats.total_locations}</div>
                  <div className="text-sm text-gray-500">Locations</div>
                </div>
                <div className="bg-white rounded-lg shadow p-4 text-center">
                  <Instagram className="w-8 h-8 mx-auto mb-2 text-purple-500" />
                  <div className="text-2xl font-bold">{stats.total_accounts}</div>
                  <div className="text-sm text-gray-500">Accounts</div>
                </div>
                <div className="bg-white rounded-lg shadow p-4 text-center">
                  <Hash className="w-8 h-8 mx-auto mb-2 text-orange-500" />
                  <div className="text-2xl font-bold">{stats.total_hashtags}</div>
                  <div className="text-sm text-gray-500">Hashtags</div>
                </div>
                <div className="bg-white rounded-lg shadow p-4 text-center">
                  <Users className="w-8 h-8 mx-auto mb-2 text-pink-500" />
                  <div className="text-2xl font-bold">{stats.total_faces_detected}</div>
                  <div className="text-sm text-gray-500">Faces Detected</div>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-8 h-8 animate-spin" />
              </div>
            )}
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="flex h-screen">
      <Sidebar onNavigate={setCurrentView} currentView={currentView} />
      <main className="flex-1 flex flex-col overflow-hidden bg-gray-100">
        {renderContent()}
      </main>
    </div>
  );
}
