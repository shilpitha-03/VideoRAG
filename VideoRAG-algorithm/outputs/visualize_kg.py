#!/usr/bin/env python3
import os
import json
import argparse
import webbrowser
from http.server import SimpleHTTPRequestHandler, HTTPServer
import threading
import time

def parse_kg_json(file_path):
    """
    Parses the knowledge graph JSON and formats it for Cytoscape.js consumption.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Error: The file '{file_path}' does not exist.")

    with open(file_path, "r", encoding="utf-8") as f:
        graph_data = json.load(f)

    elements = []

    # 1. Map entities to graph nodes
    for node_name, node_info in graph_data.get("entities", {}).items():
        clean_id = node_name.strip('"')
        entity_type = node_info.get("entity_type", "CONCEPT").strip('"')
        elements.append({
            "data": {
                "id": clean_id,
                "label": clean_id,
                "type": entity_type
            }
        })

    # 2. Map connections to graph edges
    for edge in graph_data.get("relationships", []):
        source = edge.get("source", "").strip('"')
        target = edge.get("target", "").strip('"')
        weight = float(edge.get("weight", 1.0))
        full_description = edge.get("description", "").strip('"')
        
        # Generate a short truncated label for initial rendering
        short_label = full_description[:25] + "..." if len(full_description) > 25 else full_description
        
        if source and target:
            elements.append({
                "data": {
                    "id": f"{source}-{target}",
                    "source": source,
                    "target": target,
                    "weight": weight,
                    "short_label": short_label,       
                    "full_description": full_description 
                }
            })
            
    return elements

def generate_html(elements):
    """
    Generates the complete HTML string containing the Cytoscape engine 
    and custom interactivity configurations.
    """
    html_template = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Interactive Knowledge Graph Viewer</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.26.0/cytoscape.min.js"></script>
    <style>
        html, body {{
            margin: 0;
            padding: 0;
            width: 100%;
            height: 100%;
            overflow: hidden;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: #fafafa;
        }}
        #control-panel {{
            position: absolute;
            top: 10px;
            left: 10px;
            z-index: 1000;
            background: rgba(255, 255, 255, 0.95);
            padding: 12px 20px;
            border-radius: 6px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.15);
            border: 1px solid #ccc;
        }}
        h2 {{ margin: 0 0 5px 0; font-size: 18px; color: #111; }}
        p {{ margin: 0; font-size: 12px; color: #555; }}
        #cy {{
            width: 100%;
            height: 100%;
            position: absolute;
            top: 0;
            left: 0;
            z-index: 1;
        }}
    </style>
</head>
<body>

    <div id="control-panel">
        <h2>Dynamic Hover-Expanding Knowledge Graph</h2>
        <p>✨ Move cursor over a <b>relationship textbox badge</b> to highlight paths and expand full descriptions.</p>
    </div>

    <div id="cy"></div>

    <script>
        var cyData = {json.dumps(elements)};

        var cy = cytoscape({{
            container: document.getElementById('cy'),
            elements: cyData,
            style: [
                {{
                    selector: 'node',
                    style: {{
                        'label': 'data(label)',
                        'color': '#000000',
                        'font-size': '13px',
                        'font-weight': 'bold',
                        'text-valign': 'center',
                        'text-halign': 'center',
                        'width': '125px',
                        'height': '125px',
                        'text-wrap': 'wrap',
                        'text-max-width': '110px',
                        'border-width': '2px',
                        'border-color': '#333333',
                        'transition-property': 'border-color, border-width',
                        'transition-duration': '0.15s'
                    }}
                }},
                {{ selector: 'node[type="ANATOMY"]', style: {{ 'background-color': '#4A90D9' }} }},
                {{ selector: 'node[type="INSTRUMENT"]', style: {{ 'background-color': '#E8743B' }} }},
                {{ selector: 'node[type="PROCEDURE"]', style: {{ 'background-color': '#48A23F' }} }},
                {{ selector: 'node[type="SURGICAL_STEP"]', style: {{ 'background-color': '#9B59B6' }} }},
                {{ selector: 'node[type="ANATOMICAL_LANDMARK"]', style: {{ 'background-color': '#E84393' }} }},
                {{ selector: 'node[type="PATHOLOGY"]', style: {{ 'background-color': '#E74C3C' }} }},
                {{ selector: 'node[type="UNKNOWN"]', style: {{ 'background-color': '#bbb' }} }},
                                {{
                    selector: 'edge',
                    style: {{
                        'label': 'data(short_label)',
                        'font-size': '10px',
                        'color': '#111111',
                        'font-weight': 'normal',
                        'text-wrap': 'wrap',
                        'text-max-width': '140px',
                        'text-background-opacity': 1.0,
                        'text-background-color': '#ffffff',
                        'text-background-padding': '4px',
                        'text-background-shape': 'roundrectangle',
                        'text-border-width': '1px',
                        'text-border-color': '#dddddd',
                        'width': '2.5px',
                        'line-color': '#90a4ae',
                        'target-arrow-color': '#90a4ae',
                        'target-arrow-shape': 'triangle',
                        'curve-style': 'bezier',
                        'control-point-step-size': '50px',
                        'transition-property': 'line-color, width, target-arrow-color',
                        'transition-duration': '0.15s'
                    }}
                }},
                {{
                    selector: 'edge.active-hover',
                    style: {{
                        'label': 'data(full_description)', 
                        'font-size': '11px',
                        'font-weight': 'bold',
                        'text-max-width': '260px',         
                        'text-background-color': '#fff9c4', 
                        'text-border-color': '#d32f2f',
                        'width': '6px',                     
                        'line-color': '#d32f2f',            
                        'target-arrow-color': '#d32f2f',
                        'z-index': '99999'                  
                    }}
                }},
                {{
                    selector: 'node.node-highlight',
                    style: {{
                        'border-color': '#d32f2f',
                        'border-width': '5px'
                    }}
                }}
            ],
            layout: {{
                name: 'cose',
                idealEdgeLength: 160,
                nodeOverlap: 45,
                refresh: 20,
                fit: true,
                padding: 40,
                nodeRepulsion: 900000,
                gravity: 50,
                numIter: 1000
            }}
        }});

        cy.on('mouseover', 'edge', function(event) {{
            var edge = event.target;
            edge.addClass('active-hover');
            edge.source().addClass('node-highlight');
            edge.target().addClass('node-highlight');
        }});

        cy.on('mouseout', 'edge', function(event) {{
            var edge = event.target;
            edge.removeClass('active-hover');
            edge.source().removeClass('node-highlight');
            edge.target().removeClass('node-highlight');
        }});
    </script>
</body>
</html>
"""
    return html_template

def main():
    parser = argparse.ArgumentParser(description="Standalone Interactive Knowledge Graph Visualizer")
    parser.add_argument(
        "-f", "--file", 
        required=True, 
        help="Path to the knowledge graph .json configuration file to visualize"
    )
    parser.add_argument(
        "-p", "--port", 
        type=int, 
        default=8050, 
        help="Local port to serve the web interface on (default: 8050)"
    )
    args = parser.parse_args()

    httpd = None
    try:
        print(f"Reading and structural processing of data: {args.file}...")
        cy_elements = parse_kg_json(args.file)
        html_content = generate_html(cy_elements)

        output_filename = "run003.html"
        with open(output_filename, "w", encoding="utf-8") as out_file:
            out_file.write(html_content)

        server_address = ('127.0.0.1', args.port)
        
        class QuietHandler(SimpleHTTPRequestHandler):
            def log_message(self, format, *args):
                pass

        httpd = HTTPServer(server_address, QuietHandler)
        
        # Fire up server background pipeline
        server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        server_thread.start()

        url = f"http://127.0.0.1:{args.port}/{output_filename}"
        print(f"Opening interactive visualization window at: {url}")
        print(" -> Press Ctrl+C in this terminal when you want to stop the script.")
        webbrowser.open(url)

        # Loop smoothly in the main execution thread to capture KeyboardInterrupt signals
        while True:
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\nShutting down Knowledge Graph visualization engine cleanly...")
    except Exception as err:
        print(f"\nAn error occurred: {err}")
    finally:
        # Shutdown network sockets explicitly
        if httpd:
            httpd.shutdown()
            httpd.server_close()
            
        # Clean up transient workspace footprint file
        if os.path.exists("index.html"):
            try:
                os.remove("index.html")
            except OSError:
                pass
        print("Shutdown complete.")

if __name__ == "__main__":
    main()

# # To quickly swap config files and visualize a completely different knowledge graph
# python visualize_kg.py -f path/to/another_knowledge_graph.json
