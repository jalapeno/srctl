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
    """Command line interface for Jalapeno API"""
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
        
        results = ctx.obj['api'].apply(config)
        
        for result in results:
            if result['status'] == 'error':
                click.echo(f"Error for {result['name']}: {result['error']}", err=True)
                continue
                
            if verbose == 0:
                # Simple output - just name and SRv6 USID
                usid = result['data'].get('srv6_data', {}).get('srv6_usid', 'N/A')
                click.echo(f"{result['name']}: {usid}")
            elif verbose == 1:
                # More detailed - include all SRv6 data
                srv6_data = result['data'].get('srv6_data', {})
                click.echo(f"\n{result['name']}:")
                click.echo(f"  SRv6 USID: {srv6_data.get('srv6_usid', 'N/A')}")
                click.echo(f"  SID List: {srv6_data.get('srv6_sid_list', [])}")
            else:
                # Full output
                click.echo(f"\n{result['name']}:")
                click.echo(yaml.dump(result['data'], indent=2))
                
    except Exception as e:
        click.echo(f"Error applying configuration: {str(e)}", err=True)

if __name__ == '__main__':
    main() 