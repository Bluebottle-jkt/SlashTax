'use client';

import { useState } from 'react';
import {
  Users,
  Image,
  MapPin,
  Hash,
  Search,
  Upload,
  Instagram,
  BarChart3,
  ChevronLeft,
  ChevronRight,
  Settings,
  Network,
} from 'lucide-react';
import { useAppStore } from '@/lib/store';
import { cn } from '@/lib/utils';

interface SidebarProps {
  onNavigate: (view: string) => void;
  currentView: string;
}

const navItems = [
  { id: 'graph', label: 'Graph Explorer', icon: Network },
  { id: 'persons', label: 'Persons', icon: Users },
  { id: 'posts', label: 'Posts', icon: Image },
  { id: 'locations', label: 'Locations', icon: MapPin },
  { id: 'hashtags', label: 'Hashtags', icon: Hash },
  { id: 'upload', label: 'Upload', icon: Upload },
  { id: 'instagram', label: 'Instagram Import', icon: Instagram },
  { id: 'stats', label: 'Statistics', icon: BarChart3 },
];

export default function Sidebar({ onNavigate, currentView }: SidebarProps) {
  const { sidebarOpen, setSidebarOpen, stats } = useAppStore();
  const [searchQuery, setSearchQuery] = useState('');

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      onNavigate(`search?q=${encodeURIComponent(searchQuery)}`);
    }
  };

  return (
    <aside
      className={cn(
        'bg-white border-r border-gray-200 transition-all duration-300 flex flex-col',
        sidebarOpen ? 'w-64' : 'w-16'
      )}
    >
      {/* Header */}
      <div className="p-4 border-b border-gray-200 flex items-center justify-between">
        {sidebarOpen && (
          <h1 className="text-xl font-bold text-gray-900">SlashTax</h1>
        )}
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
        >
          {sidebarOpen ? (
            <ChevronLeft className="w-5 h-5" />
          ) : (
            <ChevronRight className="w-5 h-5" />
          )}
        </button>
      </div>

      {/* Search */}
      {sidebarOpen && (
        <form onSubmit={handleSearch} className="p-4 border-b border-gray-200">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none"
            />
          </div>
        </form>
      )}

      {/* Navigation */}
      <nav className="flex-1 p-2 overflow-y-auto">
        <ul className="space-y-1">
          {navItems.map((item) => (
            <li key={item.id}>
              <button
                onClick={() => onNavigate(item.id)}
                className={cn(
                  'w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-colors',
                  currentView === item.id
                    ? 'bg-primary-100 text-primary-700'
                    : 'text-gray-600 hover:bg-gray-100'
                )}
              >
                <item.icon className="w-5 h-5 flex-shrink-0" />
                {sidebarOpen && <span>{item.label}</span>}
              </button>
            </li>
          ))}
        </ul>
      </nav>

      {/* Stats summary */}
      {sidebarOpen && stats && (
        <div className="p-4 border-t border-gray-200 bg-gray-50">
          <h3 className="text-sm font-medium text-gray-500 mb-2">Database Stats</h3>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div className="flex items-center gap-1">
              <Users className="w-4 h-4 text-red-500" />
              <span>{stats.total_persons}</span>
            </div>
            <div className="flex items-center gap-1">
              <Image className="w-4 h-4 text-blue-500" />
              <span>{stats.total_posts}</span>
            </div>
            <div className="flex items-center gap-1">
              <MapPin className="w-4 h-4 text-green-500" />
              <span>{stats.total_locations}</span>
            </div>
            <div className="flex items-center gap-1">
              <Hash className="w-4 h-4 text-orange-500" />
              <span>{stats.total_hashtags}</span>
            </div>
          </div>
        </div>
      )}

      {/* Settings */}
      <div className="p-2 border-t border-gray-200">
        <button
          onClick={() => onNavigate('settings')}
          className={cn(
            'w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-colors',
            currentView === 'settings'
              ? 'bg-primary-100 text-primary-700'
              : 'text-gray-600 hover:bg-gray-100'
          )}
        >
          <Settings className="w-5 h-5" />
          {sidebarOpen && <span>Settings</span>}
        </button>
      </div>
    </aside>
  );
}
