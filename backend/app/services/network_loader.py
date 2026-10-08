import os
import glob
import json
import argparse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from geoalchemy2.elements import WKTElement
from app.config import settings
from app.models.node import Node
from app.models.pipe import Pipe
from app.models.detection import Detection
from app.models.sim_run import SimRun

def get_default_file():
    swmm_dir = os.path.join(settings.data_dir, "swmm")
    files = glob.glob(os.path.join(swmm_dir, "*_network.json"))
    if not files:
        return None
    # Sort by modification time, newest first
    files.sort(key=os.path.getmtime, reverse=True)
    return files[0]

def load_network(file_path: str, replace: bool):
    with open(file_path, 'r') as f:
        data = json.load(f)
        
    nodes = data.get('nodes', [])
    pipes = data.get('pipes', [])
    
    if not nodes:
        print("No nodes found in file")
        return
        
    engine = create_engine(settings.sync_database_url)
    Session = sessionmaker(bind=engine)
    
    with Session() as session:
        # Check existing nodes
        has_nodes = session.execute(select(Node).limit(1)).scalars().first() is not None
        
        if has_nodes:
            if not replace:
                print("Nodes exist in database. Use --replace to overwrite.")
                return
                
            # Check references
            det_res = session.execute(select(Detection).limit(1))
            if det_res.scalars().first() is not None:
                print("Cannot replace network: detections table has references to pipes.")
                return
                
            sim_res = session.execute(select(SimRun).limit(1))
            if sim_res.scalars().first() is not None:
                print("Cannot replace network: sim_runs table has references to pipes.")
                return
                
            # Delete old data
            print("Deleting existing pipes and nodes...")
            # We must delete pipes first (foreign key to nodes)
            session.execute(Pipe.__table__.delete())
            session.execute(Node.__table__.delete())
            
        print(f"Loading {len(nodes)} nodes and {len(pipes)} pipes...")
        
        # Insert nodes
        db_nodes = []
        for n in nodes:
            wkt = f"POINT({n['lon']} {n['lat']})"
            geom = WKTElement(wkt, srid=4326)
            db_nodes.append(Node(
                id=n['id'],
                geom=geom,
                ground_elevation_m=n['ground_elevation_m'],
                invert_elevation_m=n['invert_elevation_m'],
                depth_m=n['depth_m'],
                has_sensor=n['has_sensor']
            ))
        session.add_all(db_nodes)
        
        # Insert pipes
        db_pipes = []
        for p in pipes:
            # coords is a list of [lon, lat]
            coords_str = ", ".join(f"{lon} {lat}" for lon, lat in p['coords'])
            wkt = f"LINESTRING({coords_str})"
            geom = WKTElement(wkt, srid=4326)
            
            db_pipes.append(Pipe(
                id=p['id'],
                from_node=p['from_node'],
                to_node=p['to_node'],
                geom=geom,
                length_m=p['length_m'],
                diameter_m=p['diameter_m'],
                slope=p['slope'],
                manning_n=p['manning_n']
            ))
        session.add_all(db_pipes)
        
        session.commit()
        print("Done! Inserted database entities.")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=str, help="Path to network JSON file")
    parser.add_argument("--replace", action="store_true", help="Replace existing network")
    args = parser.parse_args()
    
    file_path = args.file or get_default_file()
    if not file_path:
        print("No network file found in data/swmm")
        import sys
        sys.exit(1)
        
    print(f"Using network file: {file_path}")
    load_network(file_path, args.replace)

if __name__ == "__main__":
    main()
