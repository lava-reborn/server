class lol.core.player.Upgrade extends lol.core.player.StuffManager
{
   var XMC;
   var addItem;
   var alertPan;
   var bag;
   var checkTransfer;
   var createItem;
   var dispatchEvent;
   var getStuff;
   var master;
   var neededList;
   var separateHeap;
   var transferStack;
   var upgradedList;
   var visavisBag;
   var visavisID;
   static var UPD_CLOSE = 0;
   static var UPD_UPGRADE = 1;
   function Upgrade(visavisID)
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
         if(transferObj.to == this.visavisBag && this.checkUpgrade(transferObj.item))
         {
            this.upgradeItem(transferObj.item);
         }
         else
         {
            this.applyTransfer(false);
         }
      }
      else
      {
         this.applyTransfer(false);
      }
   }
   function upgradeItem(inItem, outTypeID, _num)
   {
      var _loc2_;
      var _loc3_;
      if(inItem instanceof lol.core.objects.Heapable)
      {
         _loc2_ = lol.core.objects.Heapable(inItem);
         _loc3_ = !_num ? 0 : _loc2_.heapSize - _num;
         if(_loc3_ > 0)
         {
            this.separateHeap(_loc2_,_loc3_);
         }
      }
      this._upgradeItem(inItem,outTypeID);
   }
   function _upgradeItem(inItem, outTypeID)
   {
      var _loc3_ = inItem.id;
      var _loc2_ = new lol.server.mess.CSM_SSUpdate(lol.core.player.Upgrade.UPD_UPGRADE,new lol.data.BigUINT(new lol.data.BigUINTCluster(_loc3_)),outTypeID);
      if(this.XMC.Send(_loc2_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.upgradeAck);
      }
   }
   function upgradeAck(obj)
   {
      this.dispatchEvent({type:"upgrAck",param:obj.param});
   }
   function onDoubleClick(_item, _from)
   {
   }
   function applyTransfer(succes)
   {
      var _loc2_ = this.transferStack.shift();
      if(succes)
      {
         if(_loc2_.to == this.bag)
         {
            this.addItem(_loc2_.from,_loc2_.item,_loc2_.fromPos);
         }
         else if(_loc2_.to == this.visavisBag)
         {
         }
      }
      else if(!_loc2_.to)
      {
         this.addItem(_loc2_.from,_loc2_.item,_loc2_.fromPos);
      }
      else
      {
         this.addItem(_loc2_.from,_loc2_.item,_loc2_.pos);
      }
      false;
   }
   function checkUpgrade(item)
   {
      var _loc5_ = item.typeID;
      var _loc3_ = false;
      var _loc2_;
      var _loc4_ = this.neededList.length;
      _loc2_ = 0;
      while(_loc2_ < _loc4_)
      {
         if(this.neededList[_loc2_] == _loc5_)
         {
            _loc3_ = true;
            break;
         }
         _loc2_ = _loc2_ + 1;
      }
      return _loc3_;
   }
   function ss_propose(id)
   {
      var _loc2_ = lol.core.player.Upgrader(this.master.getPlayer(id));
      _loc2_.createAllUpgradeItems();
      var _loc3_ = _loc2_.playerInfo;
      var _loc5_ = _loc3_.name;
      this.neededList = _loc2_.neededItems;
      this.upgradedList = _loc2_.upgradedItems;
      this.visavisBag = _loc2_.equipment.bag;
      this.visavisBag.id = "visavisBag";
      this.visavisID = id;
      var _loc4_ = new lol.server.mess.CSM_SSCreate(lol.core.player.StuffManager.SESSION_UPGRADE,this.visavisID);
      if(this.XMC.Send(_loc4_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.proposeUpgradeAck);
      }
   }
   function proposeUpgradeAck(obj)
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
         _loc3_.label = "Невозможно улучшить снаряжение у " + _loc2_;
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
         _loc2_ = new lol.server.mess.CSM_SSUpdate(lol.core.player.Upgrade.UPD_CLOSE,new lol.data.BigUINT(new lol.data.BigUINTCluster(0)));
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
      lol.server.XMLCCallStack.skipCall("cmdAck",this,this.upgradeAck);
      var _loc3_ = lol.core.Master.getInstance().gamer;
      _loc3_.upgrade = null;
      super.kill();
   }
}
