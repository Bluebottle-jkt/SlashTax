import axios from 'axios';
import type {
  Person,
  Post,
  Location,
  Account,
  Hashtag,
  GraphData,
  Stats,
  SearchQuery,
  PostAnalysis,
  ImportJob,
} from '@/types';

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Persons API
export const personsApi = {
  list: async (skip = 0, limit = 100): Promise<Person[]> => {
    const { data } = await api.get('/persons/', { params: { skip, limit } });
    return data;
  },

  get: async (id: string): Promise<Person> => {
    const { data } = await api.get(`/persons/${id}`);
    return data;
  },

  create: async (person: { name: string; notes?: string }): Promise<Person> => {
    const { data } = await api.post('/persons/', person);
    return data;
  },

  createFromImage: async (formData: FormData): Promise<Person> => {
    const { data } = await api.post('/persons/from-image', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  },

  addFace: async (id: string, formData: FormData): Promise<Person> => {
    const { data } = await api.post(`/persons/${id}/face`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  },

  update: async (id: string, person: { name: string; notes?: string }): Promise<Person> => {
    const { data } = await api.put(`/persons/${id}`, person);
    return data;
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/persons/${id}`);
  },

  getNetwork: async (id: string, depth = 2): Promise<GraphData> => {
    const { data } = await api.get(`/persons/${id}/network`, { params: { depth } });
    return data;
  },

  getCoAppearances: async (id: string): Promise<{ person_id: string; person_name: string; shared_posts: number }[]> => {
    const { data } = await api.get(`/persons/${id}/co-appearances`);
    return data;
  },

  getLocations: async (id: string): Promise<{ location_id: string; location_name: string; visit_count: number }[]> => {
    const { data } = await api.get(`/persons/${id}/locations`);
    return data;
  },

  getTimeline: async (id: string): Promise<unknown[]> => {
    const { data } = await api.get(`/persons/${id}/timeline`);
    return data;
  },

  getProfile: async (id: string): Promise<unknown> => {
    const { data } = await api.get(`/persons/${id}/profile`);
    return data;
  },
};

// Posts API
export const postsApi = {
  list: async (skip = 0, limit = 100): Promise<Post[]> => {
    const { data } = await api.get('/posts/', { params: { skip, limit } });
    return data;
  },

  get: async (id: string): Promise<Post> => {
    const { data } = await api.get(`/posts/${id}`);
    return data;
  },

  upload: async (formData: FormData): Promise<PostAnalysis> => {
    const { data } = await api.post('/posts/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  },

  process: async (id: string): Promise<PostAnalysis> => {
    const { data } = await api.post(`/posts/${id}/process`);
    return data;
  },

  getFaces: async (id: string): Promise<{ person_id: string; person_name: string }[]> => {
    const { data } = await api.get(`/posts/${id}/faces`);
    return data;
  },

  getRelated: async (id: string, limit = 10): Promise<unknown[]> => {
    const { data } = await api.get(`/posts/${id}/related`, { params: { limit } });
    return data;
  },

  getAnalysis: async (id: string): Promise<unknown> => {
    const { data } = await api.get(`/posts/${id}/analysis`);
    return data;
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/posts/${id}`);
  },
};

// Graph API
export const graphApi = {
  getFullGraph: async (limit = 500): Promise<GraphData> => {
    const { data } = await api.get('/graph/', { params: { limit } });
    return data;
  },

  getStats: async (): Promise<Stats> => {
    const { data } = await api.get('/graph/stats');
    return data;
  },

  search: async (query: SearchQuery): Promise<GraphData> => {
    const { data } = await api.post('/graph/search', query);
    return data;
  },

  searchGet: async (q: string, type = 'all', limit = 50): Promise<GraphData> => {
    const { data } = await api.get('/graph/search', { params: { q, type, limit } });
    return data;
  },

  getLocations: async (skip = 0, limit = 100): Promise<Location[]> => {
    const { data } = await api.get('/graph/locations', { params: { skip, limit } });
    return data;
  },

  getHashtags: async (skip = 0, limit = 100): Promise<Hashtag[]> => {
    const { data } = await api.get('/graph/hashtags', { params: { skip, limit } });
    return data;
  },

  getAccounts: async (skip = 0, limit = 100): Promise<Account[]> => {
    const { data } = await api.get('/graph/accounts', { params: { skip, limit } });
    return data;
  },

  findPaths: async (startId: string, endId: string, maxDepth = 5): Promise<unknown> => {
    const { data } = await api.get(`/graph/paths/${startId}/${endId}`, { params: { max_depth: maxDepth } });
    return data;
  },

  getClusters: async (): Promise<unknown[]> => {
    const { data } = await api.get('/graph/clusters');
    return data;
  },

  getTimeline: async (startDate?: string, endDate?: string, limit = 100): Promise<unknown[]> => {
    const { data } = await api.get('/graph/timeline', { params: { start_date: startDate, end_date: endDate, limit } });
    return data;
  },
};

// Instagram API
export const instagramApi = {
  login: async (username: string, password: string): Promise<void> => {
    await api.post('/instagram/login', null, { params: { username, password } });
  },

  getProfile: async (username: string): Promise<Account> => {
    const { data } = await api.get(`/instagram/profile/${username}`);
    return data;
  },

  importPosts: async (
    username: string,
    maxPosts = 50,
    includeTagged = true
  ): Promise<{ job_id: string; message: string; status_url: string }> => {
    const { data } = await api.post('/instagram/import', {
      username,
      max_posts: maxPosts,
      include_tagged: includeTagged,
    });
    return data;
  },

  getImportStatus: async (jobId: string): Promise<ImportJob> => {
    const { data } = await api.get(`/instagram/import/${jobId}/status`);
    return data;
  },

  importSinglePost: async (shortcode: string): Promise<Post> => {
    const { data } = await api.post(`/instagram/post/${shortcode}`);
    return data;
  },
};

// Health check
export const healthCheck = async (): Promise<{ status: string; neo4j: string }> => {
  const { data } = await axios.get('http://localhost:8000/health');
  return data;
};

export default api;
