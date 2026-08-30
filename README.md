# 🕸️ Weave — Local-First Visual Knowledge Graph

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![PyQt5](https://img.shields.io/badge/GUI-PyQt5-41CD52?style=for-the-badge&logo=qt&logoColor=white)](https://riverbankcomputing.com/software/pyqt/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-0078D6?style=for-the-badge)](https://github.com/)
[![Local First](https://img.shields.io/badge/Storage-100%25%20Local--First-FF6B6B?style=for-the-badge)](https://localfirstweb.dev/)
[![License](https://img.shields.io/badge/License-Source--Available%20%2F%20Non--Commercial-red.svg?style=for-the-badge)](LICENSE)

> **Weave** is a fast, keyboard-friendly, local-first visual knowledge graph and concept mapping workspace. Designed for students, researchers, engineers, and visual thinkers who need structured concept modeling, revision mindmaps, and system architecture diagrams without cloud subscriptions or vendor lock-in.

---

## ✨ Key Features

### 🧠 Infinite Visual Graph Canvas
- **Zoom-Independent Crisp Typography**: Labels remain readable and cleanly proportioned at any canvas scale.
- **Force-Directed Physics Simulation**: Dynamic spring-embedder layout engine (`L`) to auto-untangle complex concept webs in real time.
- **Smooth Navigation**: Pan with middle-mouse or `Space + Drag`, ultra-responsive wheel zooming, and one-key zoom-to-fit (`F`).
- **Interactive Dot Grid**: Minimalist background grid for precise spatial orientation.

### 🏷️ Intelligent Nodes & Structured Property Schemas
- **Typed Semantic Nodes**: Categorize concepts into customizable types (`process`, `data`, `event`, `concept`, `object`, `note`, `resource`).
- **Dynamic Property Schemas**: Attach structured key-value metadata to any node with auto-injected schema fields.
- **Dedicated Markdown-ready Notes**: Expand any node with deep contextual notes directly inside the floating inspector.
- **Dockable Sticky Annotations**: Attach floating tag annotations to any node with 4 dock alignments (Top, Bottom, Left, Right).

### 🔗 Expressive Relationships & Edge Styles
- **Directional Links**: Support for unidirectional (`→`, `←`), bidirectional (`↔`), and non-directional (`—`) edges.
- **Stroke Styling**: Choose between `solid`, `dashed`, and `dotted` lines with custom stroke widths and interactive selection halos.
- **Relationship Labels & Types**: Label connections with semantic verbs (`depends on`, `triggers`, `refines`, `informs`).

### 🗂️ Visual Node Groups & Floating Text
- **Containment Groups**: Group related concept clusters with colored boundary envelopes.
- **Interactive Resizing**: Drag corner/edge resize handles with automatic membership tracking.
- **Canvas Text Callouts**: Place freeform multi-line text callouts anywhere on the canvas for section headers and annotations.

### 🔍 Deep Global Search (`Ctrl + F`)
- Search across node labels, contextual notes, custom key-value properties, edge labels, group titles, and canvas text.
- Instant canvas focus, camera centering, and step-through navigation across all matching entities.

### 📁 Built-in Workspace File Explorer (`Ctrl + E`)
- Dedicated tree view with live directory watching (`QFileSystemWatcher`).
- Effortless multi-file navigation, inline file renaming, deletion safety guards, and folder scoping.

### 🔄 Zero-Cloud Git Synchronization (`Ctrl + Alt + S`)
- **Two-Machine Personal Sync**: Sync your workspace across devices using your existing local Git configuration (SSH keys / credentials).
- **Safe Rebasing**: Automatic stage $\to$ commit $\to$ pull rebase $\to$ push workflow with conflict protection. No third-party servers required.

### 💾 Dual File Storage Engine
- **`.weave` (Standard JSON)**: Clean, transparent, version-control friendly JSON structure.
- **`.bweave` (Compressed Binary)**: Fast binary format with `zlib` compression (level 9) for compact storage and instant loading of large graphs.

### 🎨 Adaptive Light / Dark Theme Engine
- Seamless theme switching (`T`) with contrast-aware color palette containing 31 curated tones.
- Floating inspector and UI elements dynamically recalibrate for maximum readability in both bright and dark environments.

### 🖼️ High-Resolution Vector & Raster Export
- Export diagrams to **PNG**, **JPG**, or scalable vector **SVG**.
- Configurable scale multipliers (up to 8.0×), adjustable margins, and custom background options (Theme, Light, Dark, Transparent).

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.10+**
- **Git** (optional, required only for the Git Sync feature)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/weave.git
   cd weave
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On Linux / macOS:
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Launch Weave:**
   ```bash
   python main.py
   ```

---

## ⌨️ Keyboard Shortcuts

| Action | Shortcut | Description |
| :--- | :--- | :--- |
| **Add Node** | `N` | Prompts for a label and creates a node at canvas center |
| **Connect Nodes** | `C` | Initiates connection mode from the selected node |
| **Physics Simulation** | `L` | Toggles the real-time force-directed physics layout engine |
| **Deep Search** | `Ctrl + F` | Opens the search bar to query nodes, properties, and notes |
| **Fit to View** | `F` | Centers and frames all graph items in the viewport |
| **Toggle File Explorer** | `Ctrl + E` | Expands or collapses the left workspace file tree |
| **Toggle Inspector** | `Ctrl + B` | Expands or collapses the right floating properties sidebar |
| **Toggle Theme** | `T` | Switches between Light and Dark themes |
| **Copy / Paste** | `Ctrl + C` / `Ctrl + V` | Duplicates selected nodes, groups, and canvas text |
| **Save Graph** | `Ctrl + S` | Saves changes to the active `.weave` or `.bweave` file |
| **Save As** | `Ctrl + Shift + S` | Saves graph under a new filename/format |
| **Open File** | `Ctrl + O` | Opens a file picker for `.weave`, `.bweave`, or `.json` files |
| **Git Sync** | `Ctrl + Alt + S` | Executes sync sequence with the linked Git remote |
| **Delete Selected** | `Delete` / `Backspace` | Removes selected nodes, edges, groups, or text items |
| **Pan Canvas** | `Space + Drag` or `Middle Click` | Pans smoothly across the infinite canvas |
| **Zoom Canvas** | `Mouse Wheel` | Zooms in/out centered at cursor position |

---

## 📁 Project Architecture

```
Weave/
├── main.py              # Application entry point, MainWindow, menus, and overlay host
├── canvas.py            # GraphScene, CanvasView, NodeItem, EdgeItem, NodeGroup, CanvasText
├── ui.py                # Floating Sidebar inspector, SearchBar, SettingsDialog, FileExplorer
├── config.py            # Global configuration, theme definitions, schema, and defaults
├── colorpalette.py      # Theme-aware 31-swatch color palette and contrast calculator
├── gitsync.py           # Git CLI wrapper for conflict-safe two-machine synchronization
├── utils.py             # Shared UI color helpers and theme utilities
├── logo.ico             # Application icon
├── requirements.txt     # Python dependencies
└── README.md            # Project documentation
```

---

## 📦 Building a Standalone Windows Executable (.exe)

Weave can be compiled into a high-performance native Windows executable using **Nuitka**.

### 1. Install Build Dependencies
Ensure you have a C compiler installed (such as MSVC via Visual Studio Build Tools or MinGW64).
```bash
pip install -r requirements.txt
```

### 2. Compile to Standalone Folder (Recommended for Distribution)
```bash
python -m nuitka --standalone --enable-plugin=pyqt5 --windows-disable-console --windows-icon-from-ico=logo.ico --include-data-file=logo.ico=logo.ico --output-filename=Weave.exe --output-dir=dist main.py
```

### 3. Compile to Single File Executable (.exe)
```bash
python -m nuitka --onefile --enable-plugin=pyqt5 --windows-disable-console --windows-icon-from-ico=logo.ico --include-data-file=logo.ico=logo.ico --output-filename=Weave.exe --output-dir=dist main.py
```

*The generated executable will be placed in the `dist/` directory.*

---

## 📄 File Format (`.weave`)

Weave graphs are stored in clean, human-readable JSON:

```json
{
  "nodes": [
    {
      "id": "n1",
      "label": "Distributed Consensus",
      "x": 120.0,
      "y": -85.0,
      "node_type": "concept",
      "color": "#7b1fa2",
      "notes": "Raft vs Paxos comparison notes...",
      "sticky_text": "Exam Priority ⭐⭐⭐",
      "sticky_visible": true,
      "sticky_dock": "top",
      "properties": {
        "difficulty": "Hard",
        "pyq_frequency": "High"
      }
    }
  ],
  "edges": [
    {
      "id": "e1",
      "source": "n1",
      "target": "n2",
      "label": "implements",
      "direction": "→",
      "edge_type": "relationship",
      "line_style": "solid",
      "color": "#adb5bd"
    }
  ],
  "groups": [],
  "texts": [],
  "schema": {
    "node_types": {},
    "edge_types": {},
    "property_schema": {}
  }
}
```

---

## 🗺️ Roadmap & Planned Enhancements

- [ ] **Undo / Redo Stack**: Complete history rollback using `QUndoStack`.
- [ ] **Node Cross-Linking & Backlinks**: Wiki-style `@` mentions and bidirectional cross-referencing.
- [ ] **Curved / Bezier Edge Routing**: Orthogonal and Bezier spline routing for complex diagrams.
- [ ] **CSV / Markdown Table Import & Export**: Quick tabular import of flashcard and revision decks.
- [ ] **Background Asynchronous Sync**: Non-blocking worker threads (`QThread`) for heavy I/O operations.

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!
1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📜 License

This project is licensed under a **Source-Available & Non-Commercial License**.

- **Permitted**: Viewing, learning, personal non-commercial use, academic evaluation, and personal experimentation.
- **Prohibited**: Commercial exploitation, reselling, rebranding, sublicensing, or distributing as a paid product/service.

See the [LICENSE](LICENSE) file for complete terms and restrictions.
