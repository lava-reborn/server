class lol.core.mail.MailInspector
{
   var XMC;
   var _mailParam;
   var dispatchEvent;
   var inboxArray;
   var master;
   var outboxArray;
   var removeLettersArray;
   static var sInstance;
   static var singleCreation;
   static var CHKML_INBOX = 0;
   static var CHKML_OUTBOX = 1;
   static var CHKML_MAIL_PARAM = 255;
   var firstGetInbox = true;
   var firstGetOutbox = true;
   function MailInspector()
   {
      if(lol.core.mail.MailInspector.singleCreation)
      {
         this.init();
      }
   }
   static function getInstance()
   {
      if(!lol.core.mail.MailInspector.sInstance)
      {
         lol.core.mail.MailInspector.singleCreation = true;
         lol.core.mail.MailInspector.sInstance = new lol.core.mail.MailInspector();
         lol.core.mail.MailInspector.singleCreation = false;
      }
      return lol.core.mail.MailInspector.sInstance;
   }
   function init()
   {
      this.inboxArray = new Array();
      this.outboxArray = new Array();
      this.removeLettersArray = new Array();
      lol.events.LEventDispatcher.initialize(this);
      this.XMC = lol.server.XMLConnection.getInstance();
      this.master = lol.core.Master.getInstance();
      this.XMC.addEventListener("lsml",this,this.listMail_XMC);
      this.XMC.addEventListener("svml",this,this.mailParam_XMC);
      this.XMC.addEventListener("rcml",this,this.fullLetter_XMC);
   }
   function kill()
   {
      lol.core.mail.MailInspector.sInstance = null;
      delete lol.core.mail.MailInspector.sInstance;
      delete this.inboxArray;
      delete this.outboxArray;
   }
   function getMailParam()
   {
      if(!this._mailParam)
      {
         this.checkMailParam();
      }
      return this._mailParam;
   }
   function getInbox()
   {
      if(this.firstGetInbox)
      {
         this.getInboxFromServer();
         this.firstGetInbox = false;
         return undefined;
      }
      return this.inboxArray;
   }
   function getOutbox()
   {
      if(this.firstGetOutbox)
      {
         this.getOutboxFromServer();
         this.firstGetOutbox = false;
         return undefined;
      }
      return this.outboxArray;
   }
   function getFullLetter(id)
   {
      var _loc2_ = this.getLetterFromArray(id);
      if(!_loc2_.full)
      {
         this.getFullLetterFromServer(id);
      }
      return _loc2_;
   }
   function sendLetter(to, subject, type, body, itemsArray, afro, gold)
   {
      var _loc6_ = new lol.data.GDString(lol.server.XMLString.escape(to));
      var _loc9_ = new lol.data.GDString(lol.server.XMLString.escape(subject));
      var _loc7_ = new lol.data.GDString(lol.server.XMLString.escape(body));
      var _loc5_ = new Array();
      var _loc2_ = 0;
      var _loc3_;
      while(_loc2_ < itemsArray.length)
      {
         _loc3_ = itemsArray[_loc2_].item;
         _loc5_.push(new lol.data.BigUINT(new lol.data.BigUINTCluster(_loc3_.id)));
         _loc2_ = _loc2_ + 1;
      }
      var _loc8_ = new lol.server.mess.CSM_M_sndml(_loc6_,_loc9_,type,_loc7_,_loc5_,afro,gold);
      if(this.XMC.Send(_loc8_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.sendLetterAck);
         lol.server.XMLCCallStack.addCall("ctml",this,this.sendMailControlPacket_XMC);
      }
   }
   function getObjectsFromLetter(id)
   {
      var _loc2_ = new lol.server.mess.CSM_M_uldml(new lol.data.BigUINT(new lol.data.BigUINTCluster(id)));
      if(this.XMC.Send(_loc2_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.getObjectsFromLetterAck);
         lol.server.XMLCCallStack.addCall("ctml",this,this.getObjectsControlPacket_XMC);
      }
   }
   function removeLetters(idArray)
   {
      var _loc2_ = new lol.server.mess.CSM_M_rmvml(idArray);
      if(this.XMC.Send(_loc2_))
      {
         this.removeLettersArray.push(idArray);
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.removeLettersAck);
      }
   }
   function separateHeap(heap, _num)
   {
      var _loc2_ = !_num ? 0 : _num;
      var _loc3_;
      if(_loc2_ < heap.heapSize || _loc2_ != 0)
      {
         _loc3_ = new lol.server.mess.CSM_SSHeap(new lol.data.BigUINT(new lol.data.BigUINTCluster(heap.oID)),_loc2_);
         if(this.XMC.Send(_loc3_))
         {
            lol.server.XMLCCallStack.addCall("cmdAck",this,this.separateAck);
         }
      }
   }
   function separateAck(obj)
   {
      this.dispatch(lol.core.mail.MailEvent.SEPARATE_ITEM,obj.param.res);
   }
   function mailParam_XMC(obj)
   {
      var _loc3_ = obj.param.data;
      var _loc2_ = obj.param.time;
      this._mailParam = new lol.core.mail.MailParam(_loc3_,_loc2_);
      this.dispatch(lol.core.mail.MailEvent.CHECK_MAIL_PARAM_UPDATE);
   }
   function listMail_XMC(obj)
   {
      var _loc3_ = obj.param.id;
      var _loc7_ = obj.param.date;
      var _loc6_ = obj.param.name;
      var _loc5_ = obj.param.flag;
      var _loc8_ = obj.param.subj;
      var _loc10_ = this.master.gamer.playerInfo.name;
      var _loc11_;
      var _loc2_;
      var _loc4_;
      if(!this.isOutbox(_loc5_[0]))
      {
         _loc2_ = 0;
         while(_loc2_ < _loc3_.length)
         {
            _loc4_ = new lol.core.mail.LetterObject(_loc3_[_loc2_],_loc7_[_loc2_],"я",_loc6_[_loc2_],lol.server.XMLString.unescape(_loc8_[_loc2_]),_loc5_[_loc2_]);
            this.inboxArray.push(_loc4_);
            _loc2_ = _loc2_ + 1;
         }
         this.dispatch(lol.core.mail.MailEvent.UPDATE_INBOX);
      }
      else if(this.isOutbox(_loc5_[0]))
      {
         _loc2_ = 0;
         while(_loc2_ < _loc3_.length)
         {
            _loc4_ = new lol.core.mail.LetterObject(_loc3_[_loc2_],_loc7_[_loc2_],_loc6_[_loc2_],"мне",lol.server.XMLString.unescape(_loc8_[_loc2_]),_loc5_[_loc2_]);
            this.outboxArray.push(_loc4_);
            _loc2_ = _loc2_ + 1;
         }
         this.dispatch(lol.core.mail.MailEvent.UPDATE_OUTBOX);
      }
   }
   function fullLetter_XMC(obj)
   {
      var _loc4_ = obj.param.id;
      var _loc5_ = obj.param.flag;
      var _loc6_ = obj.param.date;
      var _loc7_ = obj.param.from;
      var _loc10_ = obj.param.to;
      var _loc12_ = obj.param.body;
      var _loc11_ = obj.param.items;
      var _loc8_ = obj.param.afro;
      var _loc9_ = obj.param.gold;
      var _loc3_ = this.getLetterFromArray(_loc4_);
      _loc3_.flag = obj.param.flag;
      _loc3_.to = obj.param.to;
      _loc3_.from = obj.param.from;
      _loc3_.body = lol.server.XMLString.unescape(obj.param.body);
      _loc3_.itemArray = obj.param.items;
      _loc3_.afro = obj.param.afro == undefined ? 0 : obj.param.afro;
      _loc3_.gold = obj.param.gold == undefined ? 0 : obj.param.gold;
      _loc3_.full = true;
      this.dispatch(lol.core.mail.MailEvent.UPDATE_LETTER,_loc3_);
   }
   function sendMailControlPacket_XMC(obj)
   {
      var _loc5_ = obj.param.id;
      var _loc4_ = obj.param.item;
      var _loc3_ = obj.param.code;
      if(_loc5_ == 0)
      {
         this.dispatch(lol.core.mail.MailEvent.SEND_LETTER_FAILED,_loc5_);
         return undefined;
      }
      var _loc2_ = 0;
      while(_loc2_ < _loc3_.length)
      {
         switch(_loc3_[_loc2_])
         {
            case -1:
               if(_loc2_ < 5)
               {
                  this.removeFromEquip(_loc4_[_loc2_]);
               }
               break;
            case -9:
               this.dispatch(lol.core.mail.MailEvent.SEND_LETTER_OBJECT_NOT_FOUND);
               break;
            case -11:
               this.dispatch(lol.core.mail.MailEvent.SEND_LETTER_OBJECT_CAN_NOT_BE_ATTACHED);
         }
         _loc2_ = _loc2_ + 1;
      }
   }
   function getObjectsControlPacket_XMC(obj)
   {
      var _loc6_ = obj.param.id;
      var _loc3_ = obj.param.item;
      var _loc5_ = obj.param.code;
      var _loc4_ = lol.core.mail.MailEvent.GET_OBJECTS_SUCCESS;
      var _loc2_ = 0;
      while(_loc2_ < _loc5_.length)
      {
         switch(_loc5_[_loc2_])
         {
            case -1:
               if(_loc2_ == 5)
               {
                  this.updMoney(- Number("0x" + _loc3_[_loc2_]),0);
               }
               else if(_loc2_ == 6)
               {
                  this.updMoney(0,- Number("0x" + _loc3_[_loc2_]));
               }
               this.removeItemsAndMoneyFromLetter(this.getLetterFromArray(_loc6_));
               break;
            case 1:
               if(_loc2_ < 5)
               {
                  this.addInEquip(_loc3_[_loc2_]);
               }
               else if(_loc2_ == 5)
               {
                  this.updMoney(Number("0x" + _loc3_[_loc2_]),0);
               }
               else if(_loc2_ == 6)
               {
                  this.updMoney(0,Number("0x" + _loc3_[_loc2_]));
               }
               this.removeItemsAndMoneyFromLetter(this.getLetterFromArray(_loc6_));
               break;
            case 9:
               if(_loc2_ == 5)
               {
                  this.dispatch(lol.core.mail.MailEvent.GET_OBJECTS_YOU_HAVE_NO_AFRO);
                  _loc4_ = lol.core.mail.MailEvent.GET_OBJECTS_YOU_HAVE_NO_AFRO;
               }
               else if(_loc2_ == 6)
               {
                  this.dispatch(lol.core.mail.MailEvent.GET_OBJECTS_YOU_HAVE_NO_GOLD);
                  _loc4_ = lol.core.mail.MailEvent.GET_OBJECTS_YOU_HAVE_NO_GOLD;
               }
               break;
            case 11:
               this.dispatch(lol.core.mail.MailEvent.GET_OBJECTS_FAILED);
               _loc4_ = lol.core.mail.MailEvent.GET_OBJECTS_FAILED;
         }
         _loc2_ = _loc2_ + 1;
      }
      if(_loc4_ == lol.core.mail.MailEvent.GET_OBJECTS_SUCCESS)
      {
         this.dispatch(lol.core.mail.MailEvent.GET_OBJECTS_SUCCESS);
      }
   }
   function removeItemsAndMoneyFromLetter(letterObj)
   {
      letterObj.attachObject = false;
      letterObj.itemArray = null;
      letterObj.afro = 0;
      letterObj.gold = 0;
   }
   function checkMailParam()
   {
      var _loc2_ = new lol.server.mess.CSM_M_chkml(lol.core.mail.MailInspector.CHKML_MAIL_PARAM);
      if(this.XMC.Send(_loc2_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.checkMailParamAck);
      }
   }
   function checkMailParamAck(resObj)
   {
      var _loc2_ = resObj.param.res;
      if(_loc2_ == 0)
      {
         this.dispatch(lol.core.mail.MailEvent.CHECK_MAIL_PARAM_SUCCESS);
      }
   }
   function getFullLetterFromServer(id)
   {
      var _loc2_ = new lol.server.mess.CSM_M_getml(new lol.data.BigUINT(new lol.data.BigUINTCluster(id)));
      if(this.XMC.Send(_loc2_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.getFullLetterFromServerAck);
      }
   }
   function getFullLetterFromServerAck(resObj)
   {
      var _loc2_ = resObj.param.res;
      if(_loc2_ == 0)
      {
         this.dispatch(lol.core.mail.MailEvent.GET_LETTER_BODY_SUCCESS);
      }
      else if(_loc2_ == 35)
      {
         this.dispatch(lol.core.mail.MailEvent.LETTER_NOT_FOUND);
      }
      else if(_loc2_ == 2)
      {
         this.dispatch(lol.core.mail.MailEvent.GET_LETTER_BODY_BAN);
      }
   }
   function getInboxFromServer()
   {
      var _loc2_ = new lol.server.mess.CSM_M_chkml(lol.core.mail.MailInspector.CHKML_INBOX);
      if(this.XMC.Send(_loc2_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.getInboxFromServerAck);
      }
   }
   function getInboxFromServerAck(resObj)
   {
      var _loc2_ = resObj.param.res;
      if(_loc2_ == 0)
      {
         this.dispatch(lol.core.mail.MailEvent.GET_INBOX_SUCCESS);
      }
   }
   function getOutboxFromServer()
   {
      var _loc2_ = new lol.server.mess.CSM_M_chkml(lol.core.mail.MailInspector.CHKML_OUTBOX);
      if(this.XMC.Send(_loc2_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.getOutboxFromServerAck);
      }
   }
   function getOutboxFromServerAck(resObj)
   {
      var _loc2_ = resObj.param.res;
      if(_loc2_ == 0)
      {
         this.dispatch(lol.core.mail.MailEvent.GET_OUTBOX_SUCCESS);
      }
   }
   function sendLetterAck(resObj)
   {
      var _loc2_ = resObj.param.res;
      switch(_loc2_)
      {
         case 0:
            this.dispatch(lol.core.mail.MailEvent.SEND_LETTER_SUCCESS);
            break;
         case 2:
            this.dispatch(lol.core.mail.MailEvent.SEND_LETTER_BAN);
            break;
         case 34:
            this.dispatch(lol.core.mail.MailEvent.SEND_LETTER_USER_NOT_FOUND);
            break;
         case 37:
            this.dispatch(lol.core.mail.MailEvent.SEND_LETTER_YOU_NOT_CLANER);
      }
      if(_loc2_ != 0)
      {
         lol.server.XMLCCallStack.skipCall("ctml",this,this.sendMailControlPacket_XMC);
      }
   }
   function getObjectsFromLetterAck(resObj)
   {
      var _loc2_ = resObj.param.res;
      switch(_loc2_)
      {
         case 0:
            this.dispatch(lol.core.mail.MailEvent.GET_OBJECTS_SUCCESS);
            break;
         case 2:
            this.dispatch(lol.core.mail.MailEvent.GET_OBJECTS_BAN);
            break;
         case 35:
            this.dispatch(lol.core.mail.MailEvent.GET_OBJECTS_LETTER_NOT_FOUND);
            break;
         case 36:
            this.dispatch(lol.core.mail.MailEvent.GET_OBJECTS_NO_OBJECTS);
      }
      if(_loc2_ != 0)
      {
         lol.server.XMLCCallStack.skipCall("ctml",this,this.getObjectsControlPacket_XMC);
      }
   }
   function removeLettersAck(resObj)
   {
      var _loc4_ = resObj.param.res;
      var _loc3_;
      var _loc2_;
      switch(_loc4_)
      {
         case 0:
            this.dispatch(lol.core.mail.MailEvent.REMOVE_LETTER_SUCCESS);
            _loc3_ = this.removeLettersArray.pop();
            _loc2_ = 0;
            while(_loc2_ < _loc3_.length)
            {
               this.removeLetterFromArray(_loc3_[_loc2_]);
               _loc2_ = _loc2_ + 1;
            }
            this.dispatch(lol.core.mail.MailEvent.UPDATE_INBOX);
            this.dispatch(lol.core.mail.MailEvent.UPDATE_OUTBOX);
            break;
         case 2:
            this.dispatch(lol.core.mail.MailEvent.REMOVE_LETTER_BAN);
         default:
            return;
      }
   }
   function removeLetterFromArray(id)
   {
      var _loc2_ = this.getLetterIndex(id,"inbox");
      if(_loc2_ != undefined)
      {
         this.inboxArray.splice(_loc2_,1);
      }
      else
      {
         _loc2_ = this.getLetterIndex(id,"outbox");
         this.outboxArray.splice(_loc2_,1);
      }
      this.dispatch(lol.core.mail.MailEvent.REMOVE_INBOX_LETTER,id);
   }
   function getLetterIndex(id, type)
   {
      var _loc3_ = this[type + "Array"];
      var _loc2_ = 0;
      while(_loc2_ < _loc3_.length)
      {
         if(_loc3_[_loc2_].id == id)
         {
            return _loc2_;
         }
         _loc2_ = _loc2_ + 1;
      }
   }
   function getLetterFromArray(id)
   {
      var _loc2_ = this.getLetterFromArrayType(id,"inbox");
      if(_loc2_)
      {
         return _loc2_;
      }
      _loc2_ = this.getLetterFromArrayType(id,"outbox");
      if(_loc2_)
      {
         return _loc2_;
      }
   }
   function getLetterFromArrayType(id, type)
   {
      var _loc3_ = this[type + "Array"];
      var _loc4_;
      var _loc2_ = 0;
      while(_loc2_ < _loc3_.length)
      {
         if(_loc3_[_loc2_].id == id)
         {
            _loc4_ = _loc3_[_loc2_];
            return _loc4_;
         }
         _loc2_ = _loc2_ + 1;
      }
      return _loc4_;
   }
   function dispatch(type, param)
   {
      this.dispatchEvent(new lol.core.mail.MailEvent(type,param));
   }
   function isOutbox(flag)
   {
      var _loc1_ = Boolean(flag >> 7 & 1);
      return _loc1_;
   }
   function updMoney(afro, gold)
   {
      var _loc1_ = lol.core.Master.getInstance().gamer;
      var _loc2_ = afro != undefined ? afro : 0;
      var _loc3_ = gold != undefined ? gold : 0;
      if(_loc2_ != 0 || _loc3_ != 0)
      {
         _loc1_.setMoney(_loc1_.attributes.afro + _loc2_,_loc1_.attributes.gold + _loc3_);
      }
   }
   function addInEquip(oid)
   {
      var _loc1_ = lol.core.Master.getInstance().gamer.equipment;
      var _loc2_ = _loc1_.createItem(oid);
      lol.core.objects.ItemFactory.requestSD(oid);
      _loc1_.addItem(_loc1_.bag,_loc2_);
   }
   function removeFromEquip(oid)
   {
      var _loc1_ = lol.core.Master.getInstance().gamer.equipment;
      var _loc2_ = _loc1_.findItem(oid);
      _loc1_.removeItem(_loc2_.slot,_loc2_.item);
   }
}
