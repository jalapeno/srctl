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
                click.echo(f"\n{result['name']} (found {total_paths} paths):")
                for i, path in enumerate(paths, 1):
                    srv6_data = path.get('srv6_data', {})
                    click.echo(f"  Path {i} SRv6 uSID: {srv6_data.get('srv6_usid', 'N/A')}")
            
            elif verbose == 1:
                # More detailed output
                click.echo(f"\n{result['name']} (found {total_paths} paths):")
                for i, path in enumerate(paths, 1):
                    srv6_data = path.get('srv6_data', {})
                    click.echo(f"  Path {i}:")
                    click.echo(f"    SRv6 USID: {srv6_data.get('srv6_usid', 'N/A')}")
                    click.echo(f"    SID List: {srv6_data.get('srv6_sid_list', [])}")
                    click.echo(f"    Hop Count: {path.get('hopcount', 'N/A')}")
                    if path.get('countries_traversed'):
                        countries = [c for sublist in path['countries_traversed'] if sublist for c in sublist]
                        click.echo(f"    Countries: {', '.join(countries)}")
            
            else:
                # Full output
                click.echo(f"\n{result['name']}:")
                click.echo(yaml.dump(result['data'], indent=2))
                
    except Exception as e:
        click.echo(f"Error getting paths: {str(e)}", err=True)
        if verbose > 0:
            import traceback
            click.echo(traceback.format_exc(), err=True)

if __name__ == '__main__':
    main() 