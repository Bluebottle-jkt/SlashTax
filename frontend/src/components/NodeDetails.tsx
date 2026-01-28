'use client';

import { useState, useEffect } from 'react';
import { X, User, Image, MapPin, Hash, AtSign, ExternalLink } from 'lucide-react';
import type { GraphNode } from '@/types';
import { personsApi, postsApi } from '@/lib/api';
import { cn, formatDate, getNodeTypeColor } from '@/lib/utils';

interface NodeDetailsProps {
  node: GraphNode;
  onClose: () => void;
  onExploreNetwork?: (nodeId: string) => void;
}

export default function NodeDetails({ node, onClose, onExploreNetwork }: NodeDetailsProps) {
  const [details, setDetails] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDetails = async () => {
      setLoading(true);
      try {
        if (node.type === 'Person') {
          const profile = await personsApi.getProfile(node.id);
          setDetails(profile);
        } else if (node.type === 'Post') {
          const analysis = await postsApi.getAnalysis(node.id);
          setDetails(analysis);
        } else {
          setDetails(node.properties);
        }
      } catch (error) {
        console.error('Error fetching details:', error);
        setDetails(node.properties);
      }
      setLoading(false);
    };

    fetchDetails();
  }, [node]);

  const getIcon = () => {
    switch (node.type) {
      case 'Person':
        return <User className="w-6 h-6" />;
      case 'Post':
        return <Image className="w-6 h-6" />;
      case 'Location':
        return <MapPin className="w-6 h-6" />;
      case 'Account':
        return <AtSign className="w-6 h-6" />;
      case 'Hashtag':
        return <Hash className="w-6 h-6" />;
      default:
        return null;
    }
  };

  return (
    <div className="absolute right-0 top-0 h-full w-96 bg-white shadow-xl border-l border-gray-200 overflow-y-auto">
      {/* Header */}
      <div className="sticky top-0 bg-white border-b border-gray-200 p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={cn('p-2 rounded-lg', getNodeTypeColor(node.type))}>
            {getIcon()}
          </div>
          <div>
            <h2 className="font-semibold text-gray-900">{node.label}</h2>
            <span className={cn('text-xs px-2 py-0.5 rounded-full', getNodeTypeColor(node.type))}>
              {node.type}
            </span>
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Content */}
      <div className="p-4">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <div className="spinner" />
          </div>
        ) : (
          <>
            {/* Person Details */}
            {node.type === 'Person' && details && (
              <div className="space-y-4">
                {details.person?.profile_image && (
                  <img
                    src={details.person.profile_image}
                    alt={node.label}
                    className="w-24 h-24 rounded-full mx-auto object-cover"
                  />
                )}

                {details.profile && (
                  <div className="bg-gray-50 p-3 rounded-lg">
                    <h3 className="text-sm font-medium text-gray-500 mb-1">AI Profile</h3>
                    <p className="text-sm text-gray-700">{details.profile}</p>
                  </div>
                )}

                <div>
                  <h3 className="text-sm font-medium text-gray-500 mb-2">Statistics</h3>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="bg-blue-50 p-2 rounded-lg text-center">
                      <div className="text-lg font-semibold text-blue-700">
                        {details.person?.post_count || 0}
                      </div>
                      <div className="text-xs text-blue-600">Appearances</div>
                    </div>
                    <div className="bg-green-50 p-2 rounded-lg text-center">
                      <div className="text-lg font-semibold text-green-700">
                        {details.locations?.length || 0}
                      </div>
                      <div className="text-xs text-green-600">Locations</div>
                    </div>
                  </div>
                </div>

                {details.co_appearances?.length > 0 && (
                  <div>
                    <h3 className="text-sm font-medium text-gray-500 mb-2">
                      Frequently Appears With
                    </h3>
                    <ul className="space-y-1">
                      {details.co_appearances.slice(0, 5).map((person: any) => (
                        <li
                          key={person.person_id}
                          className="flex items-center justify-between text-sm bg-gray-50 p-2 rounded"
                        >
                          <span>{person.person_name}</span>
                          <span className="text-gray-500">{person.shared_posts} posts</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {details.locations?.length > 0 && (
                  <div>
                    <h3 className="text-sm font-medium text-gray-500 mb-2">Locations Visited</h3>
                    <ul className="space-y-1">
                      {details.locations.slice(0, 5).map((loc: any) => (
                        <li
                          key={loc.location_id}
                          className="flex items-center gap-2 text-sm bg-gray-50 p-2 rounded"
                        >
                          <MapPin className="w-4 h-4 text-green-600" />
                          <span>{loc.location_name}</span>
                          <span className="text-gray-500 ml-auto">{loc.visit_count}x</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {/* Post Details */}
            {node.type === 'Post' && details && (
              <div className="space-y-4">
                {details.post?.caption && (
                  <div>
                    <h3 className="text-sm font-medium text-gray-500 mb-1">Caption</h3>
                    <p className="text-sm text-gray-700">{details.post.caption}</p>
                  </div>
                )}

                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div className="bg-gray-50 p-2 rounded">
                    <span className="text-gray-500">Likes:</span>{' '}
                    <span className="font-medium">{details.post?.likes || 0}</span>
                  </div>
                  <div className="bg-gray-50 p-2 rounded">
                    <span className="text-gray-500">Comments:</span>{' '}
                    <span className="font-medium">{details.post?.comments || 0}</span>
                  </div>
                </div>

                {details.posted_at && (
                  <div className="text-sm text-gray-500">
                    Posted: {formatDate(details.post?.posted_at)}
                  </div>
                )}

                {details.persons?.length > 0 && (
                  <div>
                    <h3 className="text-sm font-medium text-gray-500 mb-2">People in Post</h3>
                    <div className="flex flex-wrap gap-1">
                      {details.persons.map((name: string, idx: number) => (
                        <span
                          key={idx}
                          className="px-2 py-1 bg-red-100 text-red-700 rounded-full text-xs"
                        >
                          {name}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {details.hashtags?.length > 0 && (
                  <div>
                    <h3 className="text-sm font-medium text-gray-500 mb-2">Hashtags</h3>
                    <div className="flex flex-wrap gap-1">
                      {details.hashtags.map((tag: string) => (
                        <span
                          key={tag}
                          className="px-2 py-1 bg-orange-100 text-orange-700 rounded-full text-xs"
                        >
                          #{tag}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Generic Details */}
            {!['Person', 'Post'].includes(node.type) && details && (
              <div className="space-y-2">
                {Object.entries(details).map(([key, value]) => (
                  <div key={key} className="flex justify-between text-sm">
                    <span className="text-gray-500">{key}:</span>
                    <span className="font-medium">{String(value)}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Actions */}
            {node.type === 'Person' && onExploreNetwork && (
              <button
                onClick={() => onExploreNetwork(node.id)}
                className="mt-4 w-full flex items-center justify-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
              >
                <ExternalLink className="w-4 h-4" />
                Explore Network
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
}
