# taowuDB (梼杌DB)

Self-developed relational database system with MySQL wire protocol compatibility.

## Architecture

```
config_gui (PyQt GUI)  ←→  taowu (core engine)
     frontend                  backend (config logic library)
```

- **Backend `taowu/`**: Storage engine (B+ tree), SQL engine, MySQL protocol, transactions, config manager
- **Frontend `config_gui/`**: Desktop GUI for configuration management, monitoring, and query editing
- **Logic separation**: All utilities, logic, and rules are strictly split into backend logic (`taowu/config/`) and frontend logic (`config_gui/utils/`)

## Quick Start

```bash
# Install
pip install -e .

# Initialize database
python scripts/init_db.py

# Start server
taowudb --port 3307

# Connect with MySQL client
mysql -h 127.0.0.1 -P 3307 -u root

# Launch GUI
taowudb-gui
```

## Features (v0.1)

- Basic SQL engine (CREATE/DROP/INSERT/SELECT/UPDATE/DELETE)
- Page-based B+ tree storage engine with WAL
- MySQL wire protocol v10 compatibility
- Transaction support (ACID with MVCC)
- PyQt desktop GUI for management and monitoring
