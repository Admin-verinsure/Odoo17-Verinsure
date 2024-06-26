# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
#    Copyright (C) 2013 Julius Network Solutions SARL <contact@julius.fr>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import time
import logging

_logger = logging.getLogger('smsclient')

class ServerAction(models.Model):
    """
    Possibility to specify the SMS Gateway when configure this server action
    """
    _inherit = 'ir.actions.server'

    action_type = fields.Selection([('sms','SMS')], 'action Type')
    sms =  fields.Char('sms')
    mobile = fields.Char('Mobile')
    condition =  fields.Char('Condition')
    sms_server = fields.Many2one('sms.smsclient', 'SMS Server',
            help='Select the SMS Gateway configuration to use with this action')
    sms_template_id  = fields.Many2one('mail.template', 'SMS Template',
            help='Select the SMS Template configuration to use with this action')


    @api.model
    def run(self):
        context = self._context
        if self._context is None:
            self._context = {}
        act_ids = []
        for action in self:
            obj_pool = self.env[action.model_id.model]
            obj = obj_pool.browse(self._context.get('active_id', False))
            email_template_obj = self.env['mail.template']
            cxt = {
                'context': self._context,
                'object': obj,
                'time': time,
                'cr': self._cr,
                'pool': self.env,
                'uid': self._uid,
            }
            expr = eval(str(action.condition), cxt)
            if not expr:
                continue
            if action.state == 'sms':
                _logger.info('Send SMS')
                sms_pool = self.env['sms.smsclient']
                queue_obj = self.env['sms.smsclient.queue']
                mobile = str(action.mobile)
                to = None
                try:
                    cxt.update({'gateway': action.sms_server})
                    gateway = action.sms_template_id.gateway_id
                    if mobile:
                        to = eval(action.mobile, cxt)
                    res_id = self._context.get('active_id')
                    template = email_template_obj.get_email_template(action.sms_template_id.id, res_id, self._context)
                    values = {}
                    for field in ['subject', 'body_html', 'email_from',
                                  'email_to', 'email_recipients', 'email_cc', 'reply_to']:
                        values[field] = email_template_obj.render_template( getattr(template, field),
                                                             template.model, res_id, context=context) \
                                                             or False
                    vals ={
                        'name': gateway.url,
                        'gateway_id': gateway.id,
                        'state': 'draft',
                        'mobile': to,
                        'msg': values['body_html'],
                        'validity': gateway.validity, 
                        'classes': gateway.classes, 
                        'deferred': gateway.deferred, 
                        'priority': gateway.priority, 
                        'coding': gateway.coding,
                        'tag': gateway.tag, 
                        'nostop': gateway.nostop,
                    }
                    sms_in_q = queue_obj.search(cr, uid,[
                        ('name','=',gateway.url),
                        ('gateway_id','=',gateway.id),
                        ('state','=','draft'),
                        ('mobile','=',to),
                        ('msg','=',values['body_html']),
                        ('validity','=',gateway.validity), 
                        ('classes','=',gateway.classes), 
                        ('deferred','=',gateway.deferred), 
                        ('priority','=',gateway.priority), 
                        ('coding','=',gateway.coding),
                        ('tag','=',gateway.tag), 
                        ('nostop','=',gateway.nostop)
                        ])
                    if not sms_in_q:
                        queue_obj.create( vals, context=context)
                        _logger.info('SMS successfully send to : %s' % (to))
                except Exception:
                    _logger.error('Failed to send SMS : %s' % repr(e))
            else:
                act_ids.append(action.id)
        if act_ids:
            return super(ServerAction, self).run(act_ids, context=context)
        return super(ServerAction, self).run()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
