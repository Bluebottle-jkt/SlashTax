export interface Person {
  id: string;
  name: string;
  notes?: string;
  face_encoding?: number[];
  profile_image?: string;
  post_count: number;
  created_at?: string;
}

export interface Post {
  id: string;
  shortcode: string;
  caption?: string;
  posted_at?: string;
  likes: number;
  comments: number;
  image_urls: string[];
  faces_detected: number;
  processed: boolean;
}

export interface Location {
  id: string;
  name: string;
  latitude?: number;
  longitude?: number;
  post_count: number;
}

export interface Account {
  id: string;
  username: string;
  full_name?: string;
  biography?: string;
  profile_pic_url?: string;
  followers: number;
  following: number;
  post_count: number;
  is_private: boolean;
}

export interface Hashtag {
  id: string;
  name: string;
  post_count: number;
}

export interface GraphNode {
  id: string;
  label: string;
  type: 'Person' | 'Post' | 'Location' | 'Account' | 'Hashtag';
  properties: Record<string, unknown>;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
  properties?: Record<string, unknown>;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface FaceDetection {
  person_id?: string;
  person_name?: string;
  confidence: number;
  bounding_box: {
    top: number;
    right: number;
    bottom: number;
    left: number;
  };
  is_new_face: boolean;
}

export interface PostAnalysis {
  post_id: string;
  faces: FaceDetection[];
  location?: Location;
  hashtags: string[];
  caption_analysis?: string;
}

export interface Stats {
  total_persons: number;
  total_posts: number;
  total_locations: number;
  total_accounts: number;
  total_hashtags: number;
  total_faces_detected: number;
  recent_posts: Post[];
}

export interface SearchQuery {
  query: string;
  search_type: 'all' | 'person' | 'location' | 'caption' | 'hashtag';
  limit: number;
}

export interface ImportJob {
  job_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  username: string;
  total_posts: number;
  processed_posts: number;
  faces_detected: number;
  errors: string[];
}
