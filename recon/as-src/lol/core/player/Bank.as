class lol.core.player.Bank extends lol.core.player.StuffManager
{
   var XMC;
   var _curWeight;
   var _maxWeight;
   var alertPan;
   var bag;
   var dispatchEvent;
   var master;
   var transferStack;
   var visavisBag;
   var visavisID;
   static var UPD_CLOSE = 0;
   static var UPD_PUT = 1;
   static var UPD_GET = 2;
   static var UPD_MAX_WEIGHT = 3;
   static var UPD_CUR_WEIGHT = 4;
   static var UPD_INCREASE_WEIGHT = 6;
   function Bank(visavisID)
   {
      super();
      this.XMC = lol.server.XMLConnection.getInstance();
      this.XMC.addEventListener("ss_upd",this);
      this.XMC.addEventListener("onClose",this,this.onClose);
      var _loc3_ = lol.core.Master.getInstance().gamer;
      this.bag = _loc3_.equipment.bag;
      this.master = lol.core.Master.getInstance();
   }
   function createSession()
   {
      lol.core.SceneShifter.closeWindow("query");
      lol.core.SceneShifter.closeWindow("alert");
      lol.core.player.NPCService.openService(this.visavisID);
      this.requestSession();
   }
   function requestSession()
   {
      var _loc2_ = 16;
      var _loc3_ = this.bag.maskIndex + _loc2_;
      this.getStuff(_loc3_);
   }
   function ss_ack(obj)
   {
      var _loc3_ = obj.param.o_list;
      var _loc4_ = false;
      var _loc5_ = new Array();
      var _loc6_ = new Array();
      var _loc7_ = _loc3_.length;
      var _loc2_ = 0;
      while(_loc2_ < _loc7_)
      {
         if(String(_loc3_[_loc2_]) == "0")
         {
            _loc4_ = true;
         }
         else if(_loc4_)
         {
            _loc6_.push(_loc3_[_loc2_]);
         }
         else
         {
            _loc5_.push(_loc3_[_loc2_]);
         }
         _loc2_ = _loc2_ + 1;
      }
      if(_loc5_.length > 0)
      {
         this.parseBag(_loc5_);
      }
      if(_loc6_.length > 0)
      {
         this.parseSession(_loc6_);
      }
   }
   function parseSession(arr)
   {
      var _loc2_ = 0;
      var _loc3_;
      var _loc4_;
      while(_loc2_ < arr.length)
      {
         _loc3_ = arr[_loc2_];
         _loc4_ = this.createItem(_loc3_);
         this.addItem(this.visavisBag,_loc4_);
         _loc2_ = _loc2_ + 1;
      }
   }
   function parseBag(arr)
   {
      var _loc2_ = 0;
      var _loc3_;
      var _loc4_;
      while(_loc2_ < arr.length)
      {
         _loc3_ = arr[_loc2_];
         _loc4_ = this.createItem(_loc3_);
         this.addItem(this.bag,_loc4_);
         _loc2_ = _loc2_ + 1;
      }
   }
   function requestTranfer(transferObj)
   {
      if(this.checkTransfer(transferObj))
      {
         if(transferObj.to == this.visavisBag)
         {
            this.putObj(transferObj.item);
         }
         else if(transferObj.to == this.bag)
         {
            this.getObj(transferObj.item);
         }
      }
      else
      {
         this.applyTransfer(false);
      }
   }
   function putObj(putItem)
   {
      var _loc3_ = lol.core.player.Bank.UPD_PUT;
      var _loc2_ = putItem.id;
      var _loc4_;
      if(_loc2_ != undefined)
      {
         _loc4_ = new lol.server.mess.CSM_SSUpdate(_loc3_,new lol.data.BigUINT(new lol.data.BigUINTCluster(_loc2_)));
         if(this.XMC.Send(_loc4_))
         {
            lol.server.XMLCCallStack.addCall("cmdAck",this,this.transferAck);
         }
      }
      else
      {
         this.applyTransfer(false);
      }
   }
   function getObj(getItem)
   {
      var _loc2_ = getItem.id;
      var _loc3_ = lol.core.player.Bank.UPD_GET;
      var _loc4_;
      if(_loc2_)
      {
         _loc4_ = new lol.server.mess.CSM_SSUpdate(_loc3_,new lol.data.BigUINT(new lol.data.BigUINTCluster(_loc2_)));
         if(this.XMC.Send(_loc4_))
         {
            lol.server.XMLCCallStack.addCall("cmdAck",this,this.transferAck);
         }
      }
      else
      {
         this.applyTransfer(false);
      }
   }
   function onDoubleClick(_item, _from)
   {
      var _loc3_;
      var _loc2_;
      if(_item)
      {
         _loc3_ = _item;
         _loc2_ = this.getSlot(_from);
         if(_loc2_ == this.bag)
         {
            this.transferItem(_loc3_,this.bag,this.visavisBag);
         }
         else if(_loc2_ == this.visavisBag)
         {
            this.transferItem(_loc3_,this.visavisBag,this.bag);
         }
      }
   }
   function increaseBank()
   {
      var _loc2_ = new lol.server.mess.CSM_SSUpdate(lol.core.player.Bank.UPD_INCREASE_WEIGHT);
      if(this.XMC.Send(_loc2_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.increaseAck);
      }
   }
   function increaseAck(obj)
   {
      var _loc1_ = obj.param.res;
      if(_loc1_ == 0)
      {
      }
   }
   function applyTransfer(succes)
   {
      var _loc2_ = this.transferStack.shift();
      if(succes)
      {
         if(_loc2_.to == this.bag)
         {
            this.removeItem(_loc2_.from,_loc2_.item);
         }
         else if(_loc2_.to == this.visavisBag)
         {
            this.dispatchEvent({type:"put"});
            this.addItem(_loc2_.to,_loc2_.item);
         }
      }
      else
      {
         this.removeItem(_loc2_.from,_loc2_.item);
         if(!_loc2_.to)
         {
            this.addItem(_loc2_.from,_loc2_.item,_loc2_.fromPos);
         }
         else
         {
            this.addItem(_loc2_.from,_loc2_.item,_loc2_.pos);
         }
      }
      if(succes)
      {
         this.dispatchEvent({type:lol.gpui.DDEvents.TRANSFER_SUCCESS});
      }
      else
      {
         this.dispatchEvent({type:lol.gpui.DDEvents.TRANSFER_ERROR});
      }
      false;
   }
   function checkUse(transferObj)
   {
      if(transferObj.item instanceof lol.core.objects.Heapable && transferObj.hitted instanceof lol.core.objects.Heapable && transferObj.from == this.bag && transferObj.to == this.bag)
      {
         if(transferObj.item.typeID == transferObj.hitted.typeID)
         {
            this.joinHeap(lol.core.objects.Heapable(transferObj.item),lol.core.objects.Heapable(transferObj.hitted));
            this.removeItem(transferObj.from,transferObj.item);
            transferObj.to = null;
            this.applyTransfer(false);
            return true;
         }
      }
      return false;
   }
   function ss_propose(id)
   {
      var _loc2_ = this.master.getPlayer(id);
      var _loc3_ = _loc2_.playerInfo;
      var _loc5_ = _loc3_.name;
      this.visavisBag = _loc2_.equipment.bag;
      this.visavisBag.id = "visavisBag";
      this.visavisID = id;
      var _loc4_ = new lol.server.mess.CSM_SSCreate(lol.core.player.StuffManager.SESSION_BANK,this.visavisID);
      if(this.XMC.Send(_loc4_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.proposeBankAck);
      }
   }
   function proposeBankAck(obj)
   {
      var _loc3_ = obj.param.res;
      var _loc2_;
      var _loc4_;
      if(_loc3_ == 0)
      {
         this.createSession();
      }
      else
      {
         _loc2_ = this.alertPan.content;
         _loc2_.label = "Невозможно воспользоваться хранилищем";
         _loc4_ = new lol.utils.Timeout(lol.core.SceneShifter,lol.core.SceneShifter.closeWindow,1000,"alert");
      }
   }
   function ss_upd(obj)
   {
      var _loc3_ = obj.param.s_status;
      var _loc4_;
      if(_loc3_ == lol.core.player.Bank.UPD_CLOSE)
      {
         this.close(obj);
      }
      else if(_loc3_ == lol.core.player.Bank.UPD_MAX_WEIGHT)
      {
         _loc4_ = obj.param.obj != undefined ? obj.param.obj : 0;
         this.maxWeight = Number("0x" + _loc4_);
         this.dispatchEvent({type:"updWeight"});
      }
      else if(_loc3_ == lol.core.player.Bank.UPD_CUR_WEIGHT)
      {
         _loc4_ = obj.param.obj != undefined ? obj.param.obj : 0;
         this.curWeight = Number("0x" + _loc4_);
         this.dispatchEvent({type:"updWeight"});
      }
   }
   function close(obj)
   {
      var _loc2_;
      if(!obj)
      {
         obj.target.removeEventListener("close",this);
         _loc2_ = new lol.server.mess.CSM_SSUpdate(lol.core.player.Barter.UPD_CLOSE,new lol.data.BigUINT(new lol.data.BigUINTCluster(0)));
         this.XMC.Send(_loc2_);
      }
      this.dispatchEvent({type:"close"});
      lol.core.SceneShifter.linkGame.visavisAvatar.removeMovieClip();
      this.kill();
   }
   function get maxWeight()
   {
      return this._maxWeight;
   }
   function set maxWeight(value)
   {
      this._maxWeight = value;
   }
   function get curWeight()
   {
      return this._curWeight;
   }
   function set curWeight(value)
   {
      this._curWeight = value;
   }
   function onClose()
   {
      this.close();
   }
   function kill()
   {
      this.XMC.removeEventListener("ss_upd",this);
      lol.server.XMLCCallStack.skipCall("ss_ack",this,this.ss_ack);
      lol.server.XMLCCallStack.skipCall("cmdAck",this,this.transferAck);
      var _loc3_ = lol.core.Master.getInstance().gamer;
      _loc3_.bank = null;
      super.kill();
   }
}
