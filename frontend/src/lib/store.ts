import { create } from 'zustand';
import type { GraphData, GraphNode, Person, Post, Stats } from '@/types';
import { graphApi, personsApi, postsApi } from './api';

interface AppState {
  // Data
  graphData: GraphData | null;
  persons: Person[];
  posts: Post[];
  stats: Stats | null;
  selectedNode: GraphNode | null;
  searchResults: GraphNode[];

  // UI State
  isLoading: boolean;
  error: string | null;
  sidebarOpen: boolean;
  graphMode: '2d' | '3d';

  // Actions
  setGraphData: (data: GraphData | null) => void;
  setPersons: (persons: Person[]) => void;
  setPosts: (posts: Post[]) => void;
  setStats: (stats: Stats | null) => void;
  setSelectedNode: (node: GraphNode | null) => void;
  setSearchResults: (results: GraphNode[]) => void;
  setIsLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setSidebarOpen: (open: boolean) => void;
  setGraphMode: (mode: '2d' | '3d') => void;

  // Async actions
  fetchGraphData: (limit?: number) => Promise<void>;
  fetchPersons: () => Promise<void>;
  fetchPosts: () => Promise<void>;
  fetchStats: () => Promise<void>;
  search: (query: string, type?: string) => Promise<void>;
  fetchPersonNetwork: (personId: string, depth?: number) => Promise<void>;
}

export const useAppStore = create<AppState>((set, get) => ({
  // Initial state
  graphData: null,
  persons: [],
  posts: [],
  stats: null,
  selectedNode: null,
  searchResults: [],
  isLoading: false,
  error: null,
  sidebarOpen: true,
  graphMode: '2d',

  // Setters
  setGraphData: (data) => set({ graphData: data }),
  setPersons: (persons) => set({ persons }),
  setPosts: (posts) => set({ posts }),
  setStats: (stats) => set({ stats }),
  setSelectedNode: (node) => set({ selectedNode: node }),
  setSearchResults: (results) => set({ searchResults: results }),
  setIsLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  setGraphMode: (mode) => set({ graphMode: mode }),

  // Async actions
  fetchGraphData: async (limit = 500) => {
    set({ isLoading: true, error: null });
    try {
      const data = await graphApi.getFullGraph(limit);
      set({ graphData: data, isLoading: false });
    } catch (error) {
      set({ error: 'Failed to fetch graph data', isLoading: false });
      console.error('Error fetching graph data:', error);
    }
  },

  fetchPersons: async () => {
    set({ isLoading: true, error: null });
    try {
      const persons = await personsApi.list();
      set({ persons, isLoading: false });
    } catch (error) {
      set({ error: 'Failed to fetch persons', isLoading: false });
      console.error('Error fetching persons:', error);
    }
  },

  fetchPosts: async () => {
    set({ isLoading: true, error: null });
    try {
      const posts = await postsApi.list();
      set({ posts, isLoading: false });
    } catch (error) {
      set({ error: 'Failed to fetch posts', isLoading: false });
      console.error('Error fetching posts:', error);
    }
  },

  fetchStats: async () => {
    try {
      const stats = await graphApi.getStats();
      set({ stats });
    } catch (error) {
      console.error('Error fetching stats:', error);
    }
  },

  search: async (query: string, type = 'all') => {
    set({ isLoading: true, error: null });
    try {
      const data = await graphApi.searchGet(query, type);
      set({ searchResults: data.nodes, isLoading: false });
    } catch (error) {
      set({ error: 'Search failed', isLoading: false });
      console.error('Error searching:', error);
    }
  },

  fetchPersonNetwork: async (personId: string, depth = 2) => {
    set({ isLoading: true, error: null });
    try {
      const data = await personsApi.getNetwork(personId, depth);
      set({ graphData: data, isLoading: false });
    } catch (error) {
      set({ error: 'Failed to fetch person network', isLoading: false });
      console.error('Error fetching person network:', error);
    }
  },
}));
