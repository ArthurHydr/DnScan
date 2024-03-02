import argparse
import dns.resolver
import dns.query
import dns.zone
from concurrent.futures import wait, ThreadPoolExecutor
import logging
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

record_types = ['A', 'AAAA', 'CNAME', 'MX', 'PTR', 'SOA', 'HINFO', 'TXT', 'SOA']

def gen_banner():
    print(""" 
+=================================================================+
|              ######     ######              #          ######   |
|   #######                                   #   ###             |
|      #     ########## ##########   ##       ####     ########## |
|      #     #        #      #      #  ##     #        #        # |
|      #            ##       #     #     ##   #               ##  |
|      #          ##        #              ## #             ##    |
| ##########    ##        ##                   #######    ##      |
+=================================================================+                                                             
| Made By: Arthur Ottoni --> github.com/arthurhydr/DnScan         |
+=================================================================+
            """)

def read_wordlist(filename):
    wordlist = []
    try:
        with open(filename, 'r') as file:
            for word in file:
                wordlist.append(word.strip())
        logger.info('Wordlist opened successfully.')
    except FileNotFoundError:
        logger.error(f'Wordlist file \'{filename}\' not found.')
        sys.exit(1)
    return wordlist

def transfer_zone(host, nameserver):
    try:
        ns_name = dns.name.from_text(nameserver)
        ns = dns.resolver.Resolver().resolve(ns_name, rdtype='A').response.answer[0][0].to_text()
        z = dns.zone.from_xfr(dns.query.xfr(ns, host))

        for name, node in z.nodes.items():
            logger.info(f'{name} {node.to_text(name)}')

        logger.info(f'Successful zone-transfer to {nameserver}')
    except dns.zone.NoSOA:
        logger.error(f'Zone-transfer failed for {nameserver}')
    except Exception as e:
        logger.error(f'Error in zone-transfer to {nameserver}')

def test_all_nameservers(host):
    try:
        resolver = dns.resolver.Resolver()
        nameservers = resolver.resolve(host, 'NS')

        return [str(nameserver.target) for nameserver in nameservers]
    except dns.resolver.NXDOMAIN:
        logger.error(f'{host} NOT FOUND.')
    except Exception as e:
        logger.error(f'Testing Error: {str(e)}')

def sub_domain_scan(host, wordlist, threads):
    with ThreadPoolExecutor(threads) as executor:
        scan = [executor.submit(sub_domain_scan_worker, host, word) for word in wordlist]
        wait(scan)

def sub_domain_scan_worker(host, word):
    try:
        ip_value = dns.resolver.resolve(f'{word}.{host}', 'A')
        if ip_value:
            logger.info(f'{word}.{host}')
    except dns.resolver.NXDOMAIN:
        pass
    except dns.resolver.NoAnswer:
        pass

def possible_takeover(host, wordlist, threads):
    with ThreadPoolExecutor(threads) as executor:
        scan = [executor.submit(possible_takeover_worker, host, word) for word in wordlist]
        wait(scan)

def possible_takeover_worker(host, word):
    try:
        answer = dns.resolver.resolve(f'{word}.{host}', 'CNAME')
        for record in answer:
            logger.info(f'{word}.{host} -> {record.to_text()}')
    except dns.resolver.NXDOMAIN:
        pass
    except dns.resolver.NoAnswer:
        pass

def dns_recon(host, wordlist, threads):
    with ThreadPoolExecutor(threads) as executor:
        scan = [executor.submit(dns_recon_worker, host, word) for word in wordlist]
        wait(scan)

def dns_recon_worker(host, word):
    for record in record_types:
        try:
            answer = dns.resolver.resolve(f'{word}.{host}', record)
            for data in answer:
                logger.info(f'{word}.{host}  {record}  -> {data.to_text()}')
        except dns.resolver.NoAnswer:
            pass
        except dns.resolver.NXDOMAIN:
            pass

def main():
    parser = argparse.ArgumentParser(description='DNS Security Testing Tool')
    parser.add_argument('host', help='Host to perform DNS tests on')
    parser.add_argument('wordlist', help='File containing a list of subdomains or keywords')
    parser.add_argument('--threads', type=int, default=50, help='Number of threads to use for scanning (default: 50)')
    parser.add_argument('--scan', choices=['subdomain', 'takeover', 'recon', 'all'], default='all', help='Type of scan to perform (default: all)')
    args = parser.parse_args()

    gen_banner()
    wordlist = read_wordlist(args.wordlist)

    try:
        print('\n------------- Zone-Transfer -------------')
        nameservers = test_all_nameservers(args.host)
        for ns_server in nameservers:
            logger.info(f'Testing nameserver: {ns_server}')
            if args.scan == 'all':
                transfer_zone(args.host, ns_server)
        
        if args.scan == 'subdomain' or args.scan == 'all':
            print('\n------------- Subdomain ---------------')
            sub_domain_scan(args.host, wordlist, args.threads)
        if args.scan == 'takeover' or args.scan == 'all':
            print('\n------------- Possible Takeover -------------')
            possible_takeover(args.host, wordlist, args.threads)
        if args.scan == 'recon' or args.scan == 'all':
            print('\n------------- DNS Recon -------------')
            dns_recon(args.host, wordlist, args.threads)

    except KeyboardInterrupt:
        quit()

if __name__ == '__main__':
    main()
