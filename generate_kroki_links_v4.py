import base64
import zlib
import sys

def generate_kroki_url(mermaid_code):
    # Encode string to bytes
    utf8_data = mermaid_code.encode('utf-8')
    # Compress with zlib (standard, includes header)
    compressed_data = zlib.compress(utf8_data, level=9)
    # Base64 encode (URL safe)
    payload = base64.urlsafe_b64encode(compressed_data).decode('utf-8')
    return f"https://kroki.io/mermaid/svg/{payload}"

# Modified Architecture Diagram with quotes in subgraph labels
arch_diagram = """graph TD
    subgraph Client ["Frontend (Browser)"]
        Vue["App.vue<br/>(Control Plane)"]
        Viewer["Rerun Viewer<br/>(Iframe / WASM)"]
    end

    subgraph Backend ["Backend Server"]
        API["API Layer<br/>(api/session.py)"]
        Session["Session Manager<br/>(core.py)"]
        DataProvider["Data Provider<br/>(data_provider.py)"]
    end

    subgraph DataInfra ["Data Infrastructure"]
        MongoDB[("Data Platform<br/>MongoDB")]
    end

    %% Control Flow
    Vue -- "1. HTTP POST /load_range" --> API
    API -- "2. session.load_range()" --> Session
    Session -- "3. DataManager.fetch_frames()" --> DataProvider
    
    %% Data Access Flow
    DataProvider -- "4. DataClient.find()" --> MongoDB
    MongoDB -- "5. Raw BSON/JSON" --> DataProvider
    DataProvider -- "6. Yield Frames" --> Session
    
    %% Rerun Streaming Flow
    Session -- "7. rr.log() -> TCP/WS" --> Viewer
    
    %% Frontend Internal
    Viewer -. "8. postMessage (Ack/Render)" .-> Vue"""

# Sequence diagram seems fine but let's regenerate it to be consistent
seq_diagram = """sequenceDiagram
    participant DP_Web as Data Platform<br/>(Web UI)
    participant Vue as App.vue<br/>(Relay Frontend)
    participant Rerun as Rerun Viewer<br/>(Iframe / WASM)
    participant DB_Service as Relay Backend<br/>(FastAPI)
    participant DP_DB as Data Platform<br/>(MongoDB)

    Note over DP_Web, DB_Service: 1. Session Initialization (Handshake)
    DP_Web->>DB_Service: POST /create_source (dataset, collection)
    DB_Service->>DB_Service: SessionManager.create_session()
    DB_Service-->>DP_Web: {<br/>    session_id: "1234",<br/>    connect_url: "rerun+http://...",<br/>    max_frames: 1000<br/>}
    DP_Web->>Vue: Open Window / Iframe (?source_uuid=1234&...)
    
    Note over Vue, Rerun: 2. Frontend Startup
    Vue->>Rerun: Load Iframe (connect_url)
    Rerun->>Vue: postMessage("rerun_ready")
    Vue->>DB_Service: POST /load_range (Initial Batch)
    
    Note over Vue, DP_DB: 3. Streaming Loop
    DB_Service->>DP_DB: Fetch Raw Data
    DP_DB-->>DB_Service: Return Documents
    DB_Service->>Rerun: Push RRD Data (WebSocket)
    Rerun->>Vue: rerun_time_update (time, is_playing)
    
    Note over Vue, Rerun: 4. User Interaction (Sync)
    Rerun->>Vue: rerun_datasource_selected (source_id, range)
    Vue->>Vue: Pause Auto Load & Wait for GC
    Vue->>DB_Service: POST /load_range (Targeted Range)
    Vue->>Rerun: rerun_set_loop_selection"""

print("Arch URL:")
print(generate_kroki_url(arch_diagram))
print("\nSeq URL:")
print(generate_kroki_url(seq_diagram))
