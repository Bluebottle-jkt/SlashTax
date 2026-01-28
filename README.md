# SlashTax - Advanced Face Recognition & Graph Analysis

A powerful application that uses Neo4j graph database for face recognition from Instagram posts, extracting information such as location, date, and caption, and visualizing relationships between people, posts, and locations.

## Features

- **Face Recognition**: Detect and identify faces in images using deep learning
- **Neo4j Graph Database**: Store and query complex relationships between entities
- **Instagram Integration**: Import posts from public Instagram profiles
- **AI-Powered Analysis**: Use Anthropic Claude and OpenAI for caption/image analysis
- **Interactive Graph Visualization**: Explore relationships in 2D/3D
- **Real-time Face Matching**: Identify known persons across multiple posts

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Next.js       │────▶│   FastAPI       │────▶│    Neo4j        │
│   Frontend      │     │   Backend       │     │    Database     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  Face Recognition   │
                    │  (dlib/face_recog)  │
                    └─────────────────────┘
```

## Graph Model

```
(Person)-[:APPEARS_IN]->(Post)
(Account)-[:POSTED]->(Post)
(Post)-[:AT_LOCATION]->(Location)
(Post)-[:HAS_HASHTAG]->(Hashtag)
```

## Prerequisites

- **Neo4j Desktop** or **Neo4j Server** (v5.x recommended)
- **Python 3.10+** with pip
- **Node.js 18+** with npm
- **CMake** and **dlib** dependencies (for face_recognition)

### Windows-specific requirements for face_recognition:
```bash
# Install Visual Studio Build Tools
# Install CMake
# Then: pip install cmake dlib face_recognition
```

## Quick Start

### 1. Start Neo4j

Download and install [Neo4j Desktop](https://neo4j.com/download/) or run via Docker:

```bash
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:5.15.0
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -e .

# Copy and configure environment
copy .env.example .env
# Edit .env with your settings

# Run the server
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

### 4. Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Neo4j Browser**: http://localhost:7474

## Docker Deployment

```bash
cd docker

# Create .env file with your API keys
echo "ANTHROPIC_API_KEY=your_key" > .env
echo "OPENAI_API_KEY=your_key" >> .env

# Start all services
docker-compose up -d
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `NEO4J_URI` | Neo4j connection URI | `bolt://localhost:7687` |
| `NEO4J_USER` | Neo4j username | `neo4j` |
| `NEO4J_PASSWORD` | Neo4j password | `password` |
| `ANTHROPIC_API_KEY` | Anthropic API key | - |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `FACE_RECOGNITION_TOLERANCE` | Face match tolerance (0-1) | `0.6` |
| `FACE_RECOGNITION_MODEL` | Detection model (`hog` or `cnn`) | `hog` |

## API Endpoints

### Persons
- `GET /api/persons/` - List all persons
- `POST /api/persons/` - Create person
- `POST /api/persons/from-image` - Create person from face image
- `GET /api/persons/{id}/network` - Get person's network graph

### Posts
- `GET /api/posts/` - List all posts
- `POST /api/posts/upload` - Upload and analyze image
- `POST /api/posts/{id}/process` - Process post for face detection

### Graph
- `GET /api/graph/` - Get full graph data
- `GET /api/graph/stats` - Get database statistics
- `GET /api/graph/search` - Search across all entities
- `GET /api/graph/paths/{start}/{end}` - Find paths between nodes

### Instagram
- `POST /api/instagram/import` - Import posts from profile
- `GET /api/instagram/import/{job_id}/status` - Check import status

## Neo4j Cypher Queries

### Find co-appearances
```cypher
MATCH (p1:Person)-[:APPEARS_IN]->(post:Post)<-[:APPEARS_IN]-(p2:Person)
WHERE p1.id < p2.id
RETURN p1.name, p2.name, count(post) as shared_posts
ORDER BY shared_posts DESC
```

### Find person's locations
```cypher
MATCH (p:Person {name: "John"})-[:APPEARS_IN]->(post:Post)-[:AT_LOCATION]->(loc:Location)
RETURN loc.name, count(post) as visits
ORDER BY visits DESC
```

### Find all connections for a person
```cypher
MATCH (p:Person {id: $person_id})-[r*1..2]-(connected)
RETURN p, r, connected
```

## Project Structure

```
SlashTax/
├── backend/
│   ├── app/
│   │   ├── api/routes/      # API endpoints
│   │   ├── core/            # Config, database
│   │   ├── services/        # Business logic
│   │   ├── schemas/         # Pydantic models
│   │   └── main.py          # FastAPI app
│   ├── pyproject.toml
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── app/             # Next.js pages
│   │   ├── components/      # React components
│   │   ├── lib/             # Utilities, API client
│   │   └── types/           # TypeScript types
│   ├── package.json
│   └── tailwind.config.js
├── docker/
│   ├── docker-compose.yml
│   ├── Dockerfile.backend
│   └── Dockerfile.frontend
├── data/
│   ├── uploads/             # Uploaded images
│   └── faces/               # Cropped face images
└── README.md
```

## Technology Stack

- **Frontend**: Next.js 14, React 18, TailwindCSS, react-force-graph
- **Backend**: FastAPI, Python 3.11, face_recognition, instaloader
- **Database**: Neo4j 5.x (Graph Database)
- **AI**: Anthropic Claude API, OpenAI API
- **Infrastructure**: Docker, Docker Compose

## Troubleshooting

### Face recognition installation issues

On Windows:
```bash
pip install cmake
pip install dlib
pip install face_recognition
```

On Linux:
```bash
sudo apt-get install cmake libopenblas-dev liblapack-dev
pip install face_recognition
```

### Neo4j connection issues

1. Ensure Neo4j is running
2. Check credentials in `.env`
3. Verify the bolt port (7687) is accessible

### Instagram rate limiting

- Use a logged-in session for more requests
- Add delays between requests
- Consider using your own Instagram account credentials

## License

MIT License
