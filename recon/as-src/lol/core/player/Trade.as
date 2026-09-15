class lol.core.player.Trade extends lol.core.player.StuffManager
{
   var XMC;
   var alertPan;
   var bag;
   var dispatchEvent;
   var master;
   var transferStack;
   var visavisBag;
   var visavisID;
   static var UPD_CLOSE = 0;
   static var UPD_BUY = 1;
   static var UPD_SELL = 2;
   static var UPD_REPAIR = 3;
   static var UPD_BUY_GOLD = 4;
   static var UPD_REPAIR_GOLD = 5;
   static var UPD_REG_TROPHY = 6;
   static var UPD_RESTORE = 7;
   static var UPD_BGPOINTS_BUY = 8;
   function Trade(visavisID)
   {
      super();
      this.XMC = lol.server.XMLConnection.getInstance();
      this.XMC.addEventListener("ss_upd",this);
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
      var _loc2_ = this.bag.maskIndex;
      this.getStuff(_loc2_);
   }
   function ss_ack(obj)
   {
      var _loc2_ = obj.param.o_list;
      if(_loc2_.length > 0)
      {
         this.parseBag(_loc2_);
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
            this.sell(transferObj.item,transferObj.heapNum);
         }
         else if(transferObj.to == this.bag)
         {
            this.buy(transferObj.item,transferObj.heapNum);
         }
      }
      else
      {
         this.applyTransfer(false);
      }
   }
   function buy(buyItem, _num)
   {
      var _loc3_ = lol.core.player.Trade.UPD_BUY;
      var _loc4_ = buyItem.getProp("g_cost");
      if(_loc4_ != 0 && _loc4_ != undefined && !isNaN(_loc4_))
      {
         _loc3_ = lol.core.player.Trade.UPD_BUY_GOLD;
      }
      var _loc5_ = 1;
      if(buyItem.rootID == lol.core.objects.Item.AMMO)
      {
         _loc5_ = _num != undefined ? _num : buyItem.getProp("size");
      }
      var _loc6_ = buyItem.tradeID.toString(16);
      if(buyItem.getProp("bg_p_cost") != undefined && !isNaN(buyItem.getProp("bg_p_cost")))
      {
         _loc3_ = lol.core.player.Trade.UPD_BGPOINTS_BUY;
      }
      var _loc7_;
      if(_loc6_ != undefined && _loc5_)
      {
         _loc7_ = new lol.server.mess.CSM_SSUpdate(_loc3_,new lol.data.BigUINT(new lol.data.BigUINTCluster(_loc6_)),_loc5_);
         if(this.XMC.Send(_loc7_))
         {
            lol.server.XMLCCallStack.addCall("cmdAck",this,this.transferAck);
         }
      }
      else
      {
         this.applyTransfer(false);
      }
   }
   function sell(sellItem, heapSizeForSell)
   {
      var _loc3_ = sellItem.id;
      var _loc4_ = lol.core.player.Trade.UPD_SELL;
      var _loc2_;
      if(sellItem instanceof lol.core.objects.Heapable)
      {
         _loc2_ = lol.core.objects.Heapable(sellItem).heapSize;
      }
      if(heapSizeForSell)
      {
         _loc2_ = heapSizeForSell;
      }
      var _loc6_;
      if(_loc3_)
      {
         _loc6_ = new lol.server.mess.CSM_SSUpdate(_loc4_,new lol.data.BigUINT(new lol.data.BigUINTCluster(_loc3_)),_loc2_);
         if(this.XMC.Send(_loc6_))
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
   function repairItem(item, gold_flag)
   {
      var _loc2_ = item.oID;
      var _loc4_;
      var _loc3_;
      if(_loc2_)
      {
         _loc4_ = !gold_flag ? lol.core.player.Trade.UPD_REPAIR : lol.core.player.Trade.UPD_REPAIR_GOLD;
         _loc3_ = new lol.server.mess.CSM_SSUpdate(_loc4_,new lol.data.BigUINT(new lol.data.BigUINTCluster(_loc2_)));
         if(this.XMC.Send(_loc3_))
         {
            lol.server.XMLCCallStack.addCall("cmdAck",this,this.repAck);
         }
      }
   }
   function restoreItem(item)
   {
      var _loc2_ = item.oID;
      var _loc3_;
      if(_loc2_)
      {
         _loc3_ = new lol.server.mess.CSM_SSUpdate(lol.core.player.Trade.UPD_RESTORE,new lol.data.BigUINT(new lol.data.BigUINTCluster(_loc2_)));
         if(this.XMC.Send(_loc3_))
         {
            lol.server.XMLCCallStack.addCall("cmdAck",this,this.repAck);
         }
      }
   }
   function repAck(obj)
   {
      this.dispatchEvent({type:"repAck",param:obj.param});
   }
   function regTrophy(item, gold_flag)
   {
      var _loc2_ = item.oID;
      var _loc3_;
      if(_loc2_)
      {
         _loc3_ = new lol.server.mess.CSM_SSUpdate(lol.core.player.Trade.UPD_REG_TROPHY,new lol.data.BigUINT(new lol.data.BigUINTCluster(_loc2_)));
         if(this.XMC.Send(_loc3_))
         {
            lol.server.XMLCCallStack.addCall("cmdAck",this,this.regAck);
         }
      }
   }
   function regAck(obj)
   {
      this.dispatchEvent({type:"regAck",param:obj.param});
   }
   function applyTransfer(succes)
   {
      var _loc2_ = this.transferStack.shift();
      var _loc3_;
      if(succes)
      {
         if(_loc2_.to == this.bag)
         {
            _loc3_ = _loc2_.item;
            this.removeItem(_loc2_.from,_loc2_.item);
            this.addItem(_loc2_.from,_loc2_.item,_loc2_.fromPos);
            this.dispatchEvent({type:"buy",item:_loc3_});
         }
         else if(_loc2_.to == this.visavisBag)
         {
            _loc3_ = _loc2_.item;
            this.dispatchEvent({type:"sell",item:_loc3_});
         }
         this.dispatchEvent({type:lol.gpui.DDEvents.TRANSFER_SUCCESS});
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
         this.dispatchEvent({type:lol.gpui.DDEvents.TRANSFER_ERROR});
      }
      false;
   }
   function checkUse(transferObj)
   {
      if(transferObj.item instanceof lol.core.objects.Heapable && transferObj.hitted instanceof lol.core.objects.Heapable)
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
      var _loc4_ = new lol.server.mess.CSM_SSCreate(1,this.visavisID);
      if(this.XMC.Send(_loc4_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.proposeTradeAck);
      }
   }
   function proposeTradeAck(obj)
   {
      var _loc2_ = obj.param.res;
      var _loc3_;
      var _loc4_;
      if(_loc2_ == 0)
      {
         this.createSession();
      }
      else
      {
         _loc3_ = this.alertPan.content;
         _loc3_.label = "Невозможно совершить бартер " + _loc2_;
         _loc4_ = new lol.utils.Timeout(lol.core.SceneShifter,lol.core.SceneShifter.closeWindow,1000,"alert");
      }
   }
   function ss_upd(obj)
   {
      var _loc2_ = obj.param.s_status;
      var _loc4_ = obj.param.obj;
      if(_loc2_ == lol.core.player.Trade.UPD_CLOSE)
      {
         this.close(obj);
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
   function kill()
   {
      this.XMC.removeEventListener("ss_upd",this);
      lol.server.XMLCCallStack.skipCall("ss_ack",this,this.ss_ack);
      lol.server.XMLCCallStack.skipCall("cmdAck",this,this.transferAck);
      var _loc3_ = lol.core.Master.getInstance().gamer;
      _loc3_.trade = null;
      super.kill();
   }
}
