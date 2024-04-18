from odoo import tools, models, fields, api, _
import logging
import requests
from requests.structures import CaseInsensitiveDict
import re
null=None

_logger = logging.getLogger(__name__)

class StockMove(models.Model):
    _inherit = "stock.picking" 


    def send_incoming(self):
        return True

    def create_update_articulo(self,p):
        url = self.env['ir.config_parameter'].sudo().get_param('digipwms.url')
        headers = CaseInsensitiveDict()
        headers["X-API-KEY"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
        new = {}
        new["CodigoArticulo"]= p.default_code
        new["Descripcion"]= p.name
        new["DiasVidaUtil"]= 9999
        new["UsaLote"]= True
        new["UsaSerie"]= False
        new["UsaVencimiento"]= False
        new["EsVirtual"]= False
        new["ArticuloTipoRotacion"]= "alta"
        new["Activo"]= True
        new["UsaPesoDeclarado"]= False
        new["PesoDeclaradoPromedio"]= 0
        resp = requests.post('%s/v1/Articulos' % url, headers=headers, json=new)
        return True

    def enviar(self):
        url = self.env['ir.config_parameter'].sudo().get_param('digipwms.url')
        headers = CaseInsensitiveDict()
        headers["X-API-KEY"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
        # Busco los envios pendiente que tiene el documento de origen de la SO
        # Genero un solo documento do SO
        # Envio cabecera
        sp = self
        newc={}
        newc["Codigo"]= re.sub('/','_',sp.name)
        newc["CodigoClienteUbicacion"]= sp.partner_id.ref
        newc["PedidoEstado"]= "pendiente"
        newc["Fecha"]= sp.create_date.strftime('%Y-%m-%d %H:%M:%S')
        newc["FechaEstimadaEntrega"]= sp.scheduled_date.strftime('%Y-%m-%d %H:%M:%S')
        newc["Observacion"]= sp.origin
        newc["Importe"]= "100"
        newc["CodigoDespacho"]= "string"
        newc["CodigoDeEnvio"]= "string"
        newc["ServicioDeEnvioTipo"]= "propio"
        newc["PedidoTag"]= ["string"]
        _logger.info('%s' % newc)
        resp = requests.post('%s/v1/Pedidos' % (url), headers=headers, json=newc)
        _logger.info(resp.content)
        # Envio detalle
        # Busco los codigos pendientes, y los pongo todos juntos, para enviarlos de una sola vez
        for det in sp.move_ids:
            new = {}
            new["CodigoPedido"] = newc['Codigo']
            new["CodigoArticulo"]= det.product_id.default_code
            new["Unidades"] = int(det.product_uom_qty)
            new["PesoDeclarado"]: 1
            new["MinimoDiasVencimiento"]: 1
            new["FechaVencimiento"]:  sp.scheduler_date.strftime('%Y-%m-%d %H:%M:%S')
            _logger.info('%s' % new)
            resp = requests.post('%s/v1/Pedidos/%s/Detalle' % (url,newc['Codigo']), headers=headers, json=new)
            _logger.info(resp.content)

    def recibir(self):
        url = self.env['ir.config_parameter'].sudo().get_param('digipwms.url')
        headers = CaseInsensitiveDict()
        headers["X-API-KEY"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
        # leo el detalle del pedido en digip
        newc={}
        newc["Codigo"]= re.sub('\/','_',self.name)
        resp = requests.get('%s/v1/Pedidos/%s/Detalle' % (url,newc['Codigo']), headers=headers) 
        if resp:
            result = eval(resp.content)
            _logger.info(result)
            # Marco las cantidades que traingo desde digip
            for det in self.move_ids:
                # Busco codigo en result
                for r in result:
                    if r['UnidadesSatisfecha']:
                        if r['CodigoArticulo'] == det.product_id.default_code:
                            det.write({'quantity_done': r['UnidadesSatisfecha']})
        return True

    def button_validate(self):        
        res = super(StockMove, self).button_validate()        
        url = self.env['ir.config_parameter'].sudo().get_param('digipwms.url')
        headers = CaseInsensitiveDict()
        headers["X-API-KEY"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
        codigo= re.sub('/','_',self.name)
        resp = requests.put('%s/v1/Pedidos/%s/Remitido' % (url,codigo), headers=headers)
        return res