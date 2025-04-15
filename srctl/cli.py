import click
import yaml
from .config import Config
from .api import JalapenoAPI

@click.group()
@click.option('--api-server', envvar='JALAPENO_API_SERVER',
              default='http://localhost:8000',
              help='Jalapeno API server address')
@click.pass_context
def main(ctx, api_server):
    """Command line interface for Segment Routing Configuration"""
    ctx.ensure_object(dict)
    ctx.obj['config'] = Config(api_server)
    ctx.obj['api'] = JalapenoAPI(ctx.obj['config'])

@main.command()
@click.option('-f', '--filename', required=True, type=click.Path(exists=True),
              help='YAML file containing the configuration')
@click.option('-v', '--verbose', count=True,
              help='Increase output verbosity (-v for detailed, -vv for full output)')
@click.pass_context
def apply(ctx, filename, verbose):
    """Apply a configuration from file"""
    try:
        with open(filename, 'r') as f:
            config = yaml.safe_load(f)
            click.echo(f"Loaded configuration from {filename}")
        
        results = ctx.obj['api'].apply(config)
        
        for result in results:
            if result['status'] == 'error':
                click.echo(f"Error for {result['name']}: {result['error']}", err=True)
                continue
                
            if verbose == 0:
                usid = result['data'].get('srv6_data', {}).get('srv6_usid', 'N/A')
                route_msg = result.get('route_programming', '')
                click.echo(f"{result['name']}: {usid} {route_msg}")
            elif verbose == 1:
                srv6_data = result['data'].get('srv6_data', {})
                click.echo(f"\n{result['name']}:")
                click.echo(f"  SRv6 USID: {srv6_data.get('srv6_usid', 'N/A')}")
                click.echo(f"  SID List: {srv6_data.get('srv6_sid_list', [])}")
                if 'route_programming' in result:
                    click.echo(f"  Route Programming: {result['route_programming']}")
            else:
                click.echo(f"\n{result['name']}:")
                click.echo(yaml.dump(result['data'], indent=2))
                if 'route_programming' in result:
                    click.echo(f"Route Programming: {result['route_programming']}")
                
    except Exception as e:
        click.echo(f"Error applying configuration: {str(e)}", err=True)
        if verbose > 0:
            import traceback
            click.echo(traceback.format_exc(), err=True)

@main.command()
@click.option('-f', '--filename', required=True, type=click.Path(exists=True),
              help='YAML file containing the configuration to delete')
@click.option('-v', '--verbose', count=True,
              help='Increase output verbosity (-v for detailed, -vv for full output)')
@click.pass_context
def delete(ctx, filename, verbose):
    """Delete a configuration from file"""
    try:
        with open(filename, 'r') as f:
            config = yaml.safe_load(f)
            click.echo(f"Loaded configuration from {filename}")
        
        results = ctx.obj['api'].delete(config)
        
        for result in results:
            if result['status'] == 'error':
                click.echo(f"Error deleting {result['name']}: {result['error']}", err=True)
                continue
                
            if verbose == 0:
                click.echo(f"{result['name']}: {result['message']}")
            elif verbose == 1:
                click.echo(f"\n{result['name']}:")
                click.echo(f"  Message: {result['message']}")
            else:
                click.echo(f"\n{result['name']}:")
                click.echo(yaml.dump(result, indent=2))
                
    except Exception as e:
        click.echo(f"Error deleting configuration: {str(e)}", err=True)
        if verbose > 0:
            import traceback
            click.echo(traceback.format_exc(), err=True)

@main.command()
@click.option('-f', '--filename', type=click.Path(exists=True),
              help='YAML file containing the path request configuration')
@click.option('-s', '--source',
              help='Source node')
@click.option('-d', '--destination',
              help='Destination node')
@click.option('-g', '--graph', default='ipv6_graph',
              help='Graph to use (default: ipv6_graph)')
@click.option('-t', '--type', 'path_type', type=click.Choice(['best-paths', 'next-best-path']),
              default='best-paths', help='Type of paths to retrieve')
@click.option('--direction', default='outbound',
              help='Direction of paths (default: outbound)')
@click.option('--limit', type=int,
              help='Limit number of paths (for best-paths)')
@click.option('--same-hop-limit', type=int,
              help='Limit number of same-hop paths (for next-best-path)')
@click.option('--plus-one-limit', type=int,
              help='Limit number of plus-one-hop paths (for next-best-path)')
@click.option('-v', '--verbose', count=True,
              help='Increase output verbosity (-v for detailed, -vv for full output)')
@click.pass_context
def get_paths(ctx, filename, source, destination, graph, path_type, direction,
              limit, same_hop_limit, plus_one_limit, verbose):
    """Get best paths between source and destination"""
    try:
        if filename:
            with open(filename, 'r') as f:
                config = yaml.safe_load(f)
                click.echo(f"Loaded configuration from {filename}")
            results = ctx.obj['api'].get_paths_from_yaml(config)
        else:
            if not source or not destination:
                raise click.UsageError("Both --source and --destination are required when not using a config file")
            
            result = ctx.obj['api'].get_paths(
                source=source,
                destination=destination,
                graph=graph,
                path_type=path_type,
                direction=direction,
                limit=limit,
                same_hop_limit=same_hop_limit,
                plus_one_limit=plus_one_limit
            )
            results = [{
                'name': f"{source}-to-{destination}",
                'status': 'success',
                'data': result
            }]
        
        # Display results
        for result in results:
            if result['status'] == 'error':
                click.echo(f"Error for {result['name']}: {result['error']}", err=True)
                continue
            
            paths = result['data'].get('paths', [])
            total_paths = result['data'].get('total_paths_found', len(paths))
            
            if verbose == 0:
                # Simple output format
                click.echo(f"\n{result['name']}:")
                
                if path_type == 'next-best-path':
                    # Handle next-best-path format
                    shortest = result['data'].get('shortest_path', {})
                    if shortest:
                        srv6_data = shortest.get('srv6_data', {})
                        click.echo(f"  Best Path SRv6 uSID: {srv6_data.get('srv6_usid', 'N/A')}")
                    
                    same_hop_paths = result['data'].get('same_hopcount_paths', [])
                    for i, path in enumerate(same_hop_paths, 1):
                        srv6_data = path.get('srv6_data', {})
                        click.echo(f"  Additional Best Path {i} SRv6 uSID: {srv6_data.get('srv6_usid', 'N/A')}")
                    
                    plus_one_paths = result['data'].get('plus_one_hopcount_paths', [])
                    for i, path in enumerate(plus_one_paths, 1):
                        srv6_data = path.get('srv6_data', {})
                        click.echo(f"  Next Best Path {i} SRv6 uSID: {srv6_data.get('srv6_usid', 'N/A')}")
                else:
                    # Handle best-paths format
                    for i, path in enumerate(paths, 1):
                        srv6_data = path.get('srv6_data', {})
                        click.echo(f"  Path {i} SRv6 uSID: {srv6_data.get('srv6_usid', 'N/A')}")
            
            elif verbose == 1:
                # More detailed output
                click.echo(f"\n{result['name']}:")
                
                if path_type == 'next-best-path':
                    # Handle next-best-path format
                    shortest = result['data'].get('shortest_path', {})
                    if shortest:
                        srv6_data = shortest.get('srv6_data', {})
                        click.echo("  Best Path:")
                        click.echo(f"    SRv6 USID: {srv6_data.get('srv6_usid', 'N/A')}")
                        click.echo(f"    SID List: {srv6_data.get('srv6_sid_list', [])}")
                        click.echo(f"    Hop Count: {shortest.get('hopcount', 'N/A')}")
                        if shortest.get('countries_traversed'):
                            countries = [c for sublist in shortest['countries_traversed'] if sublist for c in sublist]
                            click.echo(f"    Countries Traversed: {', '.join(countries)}")
                    
                    same_hop_paths = result['data'].get('same_hopcount_paths', [])
                    for i, path in enumerate(same_hop_paths, 1):
                        srv6_data = path.get('srv6_data', {})
                        click.echo(f"\n  Additional Best Path {i}:")
                        click.echo(f"    SRv6 USID: {srv6_data.get('srv6_usid', 'N/A')}")
                        click.echo(f"    SID List: {srv6_data.get('srv6_sid_list', [])}")
                        click.echo(f"    Hop Count: {path.get('hopcount', 'N/A')}")
                        if path.get('countries_traversed'):
                            countries = [c for sublist in path['countries_traversed'] if sublist for c in sublist]
                            click.echo(f"    Countries Traversed: {', '.join(countries)}")
                    
                    plus_one_paths = result['data'].get('plus_one_hopcount_paths', [])
                    for i, path in enumerate(plus_one_paths, 1):
                        srv6_data = path.get('srv6_data', {})
                        click.echo(f"\n  Next Best Path {i}:")
                        click.echo(f"    SRv6 USID: {srv6_data.get('srv6_usid', 'N/A')}")
                        click.echo(f"    SID List: {srv6_data.get('srv6_sid_list', [])}")
                        click.echo(f"    Hop Count: {path.get('hopcount', 'N/A')}")
                        if path.get('countries_traversed'):
                            countries = [c for sublist in path['countries_traversed'] if sublist for c in sublist]
                            click.echo(f"    Countries Traversed: {', '.join(countries)}")
                else:
                    # Handle best-paths format
                    paths = result['data'].get('paths', [])
                    total = result['data'].get('total_paths_found', len(paths))
                    click.echo(f"  Found {total} paths:")
                    
                    for i, path in enumerate(paths, 1):
                        srv6_data = path.get('srv6_data', {})
                        click.echo(f"\n  Path {i}:")
                        click.echo(f"    SRv6 USID: {srv6_data.get('srv6_usid', 'N/A')}")
                        click.echo(f"    SID List: {srv6_data.get('srv6_sid_list', [])}")
                        click.echo(f"    Hop Count: {path.get('hopcount', 'N/A')}")
                        if path.get('countries_traversed'):
                            countries = [c for sublist in path['countries_traversed'] if sublist for c in sublist]
                            click.echo(f"    Countries Traversed: {', '.join(countries)}")
            
            else:
                # Full output
                click.echo(f"\n{result['name']}:")
                click.echo(yaml.dump(result['data'], indent=2))
                
    except Exception as e:
        click.echo(f"Error getting paths: {str(e)}", err=True)
        if verbose > 0:
            import traceback
            click.echo(traceback.format_exc(), err=True)

@main.group()
def l3vpn():
    """L3VPN operations"""
    pass

@l3vpn.command()
@click.option('--route-target', '-rt', required=True,
              help='Route Target to query')
@click.option('--prefix', 
              help='Specific prefix to query (optional)')
@click.option('--exact-match', is_flag=True,
              help='Exact match for prefix (default: prefix match)')
@click.option('--collection', default='l3vpn_v4_prefix',
              help='Collection to query (default: l3vpn_v4_prefix)')
@click.option('--platform', required=True, type=click.Choice(['linux', 'vpp']),
              help='Platform to program routes on')
@click.option('--table-id', type=int, default=0,
              help='Table ID to program routes in (default: 0)')
@click.option('--outbound-interface', 
              help='Outbound interface (required for Linux)')
@click.option('--bsid',
              help='Binding SID (required for VPP)')
@click.option('--apply', is_flag=True,
              help='Apply the routes (default: just show them)')
@click.option('-v', '--verbose', count=True,
              help='Increase output verbosity (-v for detailed, -vv for full output)')
@click.pass_context
def get_routes(ctx, route_target, prefix, exact_match, collection, platform, 
               table_id, outbound_interface, bsid, apply, verbose):
    """Get and optionally apply L3VPN routes"""
    try:
        # Validate platform-specific parameters
        if platform == 'linux' and apply and not outbound_interface:
            raise click.UsageError("--outbound-interface is required for Linux when --apply is specified")
        if platform == 'vpp' and apply and not bsid:
            raise click.UsageError("--bsid is required for VPP when --apply is specified")
        
        # Get the routes
        if prefix:
            click.echo(f"Querying for prefix {prefix} in route-target {route_target}...")
            result = ctx.obj['api'].get_l3vpn_prefix(
                prefix=prefix,
                route_target=route_target,
                collection=collection,
                exact_match=exact_match
            )
        else:
            click.echo(f"Querying for all prefixes in route-target {route_target}...")
            result = ctx.obj['api'].get_l3vpn_prefixes_by_rt(
                route_target=route_target,
                collection=collection
            )
        
        # Display the results
        total = result.get('total_prefixes', 0)
        click.echo(f"Found {total} prefixes")
        
        if verbose == 0:
            # Simple output
            for prefix_data in result.get('prefixes', []):
                prefix = prefix_data.get('prefix')
                prefix_len = prefix_data.get('prefix_len')
                sid = prefix_data.get('sid')
                if isinstance(sid, list) and sid:
                    sid = sid[0]
                click.echo(f"  {prefix}/{prefix_len} -> {sid}")
        elif verbose == 1:
            # More detailed output
            for prefix_data in result.get('prefixes', []):
                prefix = prefix_data.get('prefix')
                prefix_len = prefix_data.get('prefix_len')
                sid = prefix_data.get('sid')
                if isinstance(sid, list) and sid:
                    sid = sid[0]
                labels = prefix_data.get('labels', [])
                nexthop = prefix_data.get('nexthop')
                click.echo(f"\n  Prefix: {prefix}/{prefix_len}")
                click.echo(f"  SID: {sid}")
                click.echo(f"  Labels: {labels}")
                click.echo(f"  Next-hop: {nexthop}")
        else:
            # Full output
            click.echo(yaml.dump(result, indent=2))
        
        # Apply the routes if requested
        if apply:
            click.echo(f"\nApplying routes to {platform}...")
            apply_results = ctx.obj['api'].apply_l3vpn_routes(
                platform=platform,
                prefixes_data=result,
                table_id=table_id,
                outbound_interface=outbound_interface,
                bsid=bsid
            )
            
            for result in apply_results:
                if result['status'] == 'error':
                    click.echo(f"Error for {result['name']}: {result['error']}", err=True)
                    continue
                    
                if verbose == 0:
                    click.echo(f"{result['name']}: {result['route_programming']}")
                elif verbose == 1:
                    click.echo(f"\n{result['name']}:")
                    click.echo(f"  Route Programming: {result['route_programming']}")
                else:
                    click.echo(f"\n{result['name']}:")
                    click.echo(yaml.dump(result['data'], indent=2))
                    click.echo(f"Route Programming: {result['route_programming']}")
                
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        if verbose > 0:
            import traceback
            click.echo(traceback.format_exc(), err=True)

if __name__ == '__main__':
    main() 