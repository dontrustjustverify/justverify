"""Internal per-client descriptor-wallet boundary; caller must authorize the client first.

No public route or wallet-mode activation is implied by this module. The RPC
adapter must use the selected profile's loopback endpoint and cookie.
"""
import re

class WalletBoundaryError(ValueError):
    pass

class WatchOnly:
    READ_METHODS=frozenset(('getwalletinfo','getbalances','getbalance','listunspent','listlockunspent','gettransaction','listtransactions','listsinceblock','getaddressinfo','listdescriptors'))

    def __init__(self,rpc,client_id):
        if not isinstance(client_id,str) or not re.fullmatch('[a-f0-9]{32}',client_id):
            raise WalletBoundaryError('Invalid client identifier')
        self.rpc=rpc
        self.name='jv-watch-'+client_id

    async def verify(self):
        info=await self.rpc('getwalletinfo',[],self.name)
        if info.get('walletname')!=self.name or info.get('private_keys_enabled') is not False or info.get('descriptors') is not True:
            raise WalletBoundaryError('Wallet is not the assigned watch-only descriptor wallet')
        return info

    async def provision(self):
        # Stable names make an interrupted create recoverable without deleting data.
        loaded=await self.rpc('listwallets',[])
        if self.name not in loaded:
            existing=await self.rpc('listwalletdir',[])
            if any(wallet.get('name')==self.name for wallet in existing['wallets']):
                await self.rpc('loadwallet',{'filename':self.name,'load_on_startup':True})
            else:
                await self.rpc('createwallet',{'wallet_name':self.name,'disable_private_keys':True,'blank':True,'descriptors':True,'load_on_startup':True})
        return await self.verify()

    async def read(self,method,params):
        if method not in self.READ_METHODS or not isinstance(params,(list,dict)):
            raise WalletBoundaryError('Method outside watch-only read scope')
        if method=='listdescriptors':
            if params not in ([],{},[False],{'private':False}):
                raise WalletBoundaryError('Private descriptor export forbidden')
            # Core 22 has no private-export argument; default is public on all versions.
            params=[]
        await self.verify()
        return await self.rpc(method,params,self.name)

    async def import_descriptors(self,requests):
        if not isinstance(requests,list) or not 1<=len(requests)<=16:
            raise WalletBoundaryError('Descriptor batch must contain 1 to 16 entries')
        await self.verify()
        checked=[]
        # Check every entry for private keys before persistent wallet mutation.
        # Core still reports other import failures per entry; imports are not atomic.
        for item in requests:
            if not isinstance(item,dict) or set(item)-{'desc','timestamp','active','internal','range','next_index','label'}:
                raise WalletBoundaryError('Unsupported descriptor fields')
            desc=item.get('desc');timestamp=item.get('timestamp')
            if not isinstance(desc,str) or not 1<=len(desc)<=16384:
                raise WalletBoundaryError('Invalid descriptor')
            if timestamp!='now' and (type(timestamp) is not int or timestamp<0):
                raise WalletBoundaryError('Invalid descriptor timestamp')
            for key in ('active','internal'):
                if key in item and type(item[key]) is not bool:raise WalletBoundaryError('Invalid descriptor flag')
            if 'label' in item and (not isinstance(item['label'],str) or len(item['label'])>128 or any(ord(c)<32 or ord(c)==127 for c in item['label'])):
                raise WalletBoundaryError('Invalid descriptor label')
            if 'range' in item:
                bounds=item['range'];bounds=[0,bounds] if type(bounds) is int else bounds
                if not isinstance(bounds,list) or len(bounds)!=2 or any(type(v) is not int for v in bounds) or not 0<=bounds[0]<=bounds[1]<=100000:
                    raise WalletBoundaryError('Invalid descriptor range')
            if 'next_index' in item and (type(item['next_index']) is not int or not 0<=item['next_index']<=100000):
                raise WalletBoundaryError('Invalid descriptor next index')
            info=await self.rpc('getdescriptorinfo',[desc])
            if info.get('hasprivatekeys') is not False:
                raise WalletBoundaryError('Private keys cannot be imported')
            checked.append({**item,'desc':info['descriptor']})
        await self.verify()
        return await self.rpc('importdescriptors',[checked],self.name)

    TRANSACTION_METHODS=frozenset(('lockunspent','walletcreatefundedpsbt','walletprocesspsbt','createpsbt','decodepsbt','analyzepsbt','combinepsbt','joinpsbts','finalizepsbt','decoderawtransaction','testmempoolaccept','sendrawtransaction'))

    async def transaction(self,method,params):
        if method not in self.TRANSACTION_METHODS or not isinstance(params,(list,dict)):
            raise WalletBoundaryError('Unsupported transaction request')
        await self.verify()
        if method=='lockunspent':
            if isinstance(params,list):
                if not 1<=len(params)<=2:raise WalletBoundaryError('Invalid coin locking arguments')
                unlock=params[0];transactions=params[1] if len(params)==2 else None
            else:
                if set(params)-{'unlock','transactions'} or 'unlock' not in params:raise WalletBoundaryError('Invalid coin locking arguments')
                unlock=params['unlock'];transactions=params.get('transactions')
            if type(unlock) is not bool:raise WalletBoundaryError('Invalid unlock flag')
            if transactions is None:
                if not unlock or (isinstance(params,list) and len(params)==2) or (isinstance(params,dict) and 'transactions' in params):raise WalletBoundaryError('Explicit coin list required')
            elif not isinstance(transactions,list) or len(transactions)>1024:
                raise WalletBoundaryError('Invalid coin list')
            else:
                for item in transactions:
                    if not isinstance(item,dict) or set(item)!={'txid','vout'} or not isinstance(item['txid'],str) or not re.fullmatch('[a-fA-F0-9]{64}',item['txid']) or type(item['vout']) is not int or not 0<=item['vout']<=0xffffffff:
                        raise WalletBoundaryError('Invalid coin outpoint')
            return await self.rpc(method,params,self.name)
        if method=='walletprocesspsbt':
            if isinstance(params,list):
                if not 1<=len(params)<=4 or (len(params)>1 and params[1] is not False):
                    raise WalletBoundaryError('Node signing is forbidden')
                params=[params[0],False,*params[2:]]
            else:
                if set(params)-{'psbt','sign','sighashtype','bip32derivs'} or 'psbt' not in params or params.get('sign',False) is not False:
                    raise WalletBoundaryError('Node signing is forbidden')
                params={**params,'sign':False}
        if method=='walletcreatefundedpsbt':
            if isinstance(params,list):
                if not 2<=len(params)<=5:raise WalletBoundaryError('Invalid funding arguments')
                options=params[3] if len(params)>3 else {}
            else:
                if set(params)-{'inputs','outputs','locktime','options','bip32derivs'} or 'outputs' not in params:raise WalletBoundaryError('Invalid funding arguments')
                options=params.get('options',{})
            if not isinstance(options,dict) or ('feeRate' in options and 'fee_rate' in options):
                raise WalletBoundaryError('Ambiguous fee units')
            if set(options)-{'add_inputs','include_unsafe','changeAddress','changePosition','change_type','includeWatching','lockUnspents','fee_rate','feeRate','subtractFeeFromOutputs','replaceable','conf_target','estimate_mode'}:
                raise WalletBoundaryError('Unsupported funding option; import public descriptors through the wallet boundary')
        return await self.rpc(method,params,self.name if method.startswith('wallet') else None)
