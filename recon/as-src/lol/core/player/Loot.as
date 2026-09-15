class lol.core.player.Loot extends lol.core.player.StuffManager
{
   var XMC;
   var bag;
   var dispatchEvent;
   var heapStack;
   var hideUI;
   var lootBag;
   var status;
   var transferStack;
   static var UPD_CLOSE = 0;
   static var UPD_TO_BAG = 1;
   static var UPD_TO_BUFFER = 2;
   static var UPD_GET_ALL = 3;
   function Loot()
   {
      super();
      this.XMC = lol.server.XMLConnection.getInstance();
      var _loc3_ = lol.core.Master.getInstance().gamer;
      this.bag = _loc3_.equipment.bag;
      this.lootBag = new lol.core.player.Bag("lootBag");
      this.heapStack = new Array();
   }
   function createSession(pos, hUI)
   {
      this.hideUI = hUI;
      var _loc2_ = new lol.server.mess.CSM_SSCreate(0,pos);
      if(this.XMC.Send(_loc2_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.ssCreated);
      }
   }
   function ssCreated(obj)
   {
      var _loc2_ = obj.param.res;
      var _loc3_;
      if(_loc2_ == 0)
      {
         if(!this.hideUI)
         {
            this.requestSession();
            _loc3_ = lol.core.SceneShifter.openNewWindow("loot");
            _loc3_.addEventListener("close",this);
         }
         this.status = true;
         this.dispatchEvent({type:"onLoot"});
      }
   }
   function close(obj)
   {
      obj.target.removeEventListener("close",this);
      var _loc2_ = new lol.server.mess.CSM_SSUpdate(lol.core.player.Loot.UPD_CLOSE,new lol.data.BigUINT(new lol.data.BigUINTCluster(0)));
      this.XMC.Send(_loc2_);
      this.kill();
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
      var _loc8_;
      var _loc9_;
      if(_loc6_.length > 0)
      {
         this.parseSession(_loc6_);
      }
      else
      {
         _loc8_ = lol.core.SceneShifter.openNewAlert("topSimple");
         _loc8_.label = "На этом месте нет предметов, которые вы можете поднять.";
         _loc9_ = new lol.utils.Timeout(lol.core.SceneShifter,lol.core.SceneShifter.closeAlert,2000,"topQuery");
         this.dispatchEvent({type:"closeWindow"});
      }
   }
   function parseSession(arr)
   {
      var _loc2_;
      var _loc3_;
      var _loc4_;
      if(arr.length > 0)
      {
         _loc2_ = 0;
         while(_loc2_ < arr.length)
         {
            _loc3_ = arr[_loc2_];
            _loc4_ = this.createItem(_loc3_);
            this.addItem(this.lootBag,_loc4_);
            _loc2_ = _loc2_ + 1;
         }
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
   function requestTranfer(transferObj)
   {
      var _loc2_;
      var _loc4_;
      if(this.checkTransfer(transferObj))
      {
         _loc2_ = transferObj.item.id;
         if(transferObj.to == this.bag)
         {
            _loc4_ = new lol.server.mess.CSM_SSUpdate(lol.core.player.Loot.UPD_TO_BAG,new lol.data.BigUINT(new lol.data.BigUINTCluster(_loc2_)));
         }
         else if(transferObj.to == this.lootBag)
         {
            _loc4_ = new lol.server.mess.CSM_SSUpdate(lol.core.player.Loot.UPD_TO_BUFFER,new lol.data.BigUINT(new lol.data.BigUINTCluster(_loc2_)));
         }
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
   function applyTransfer(succes)
   {
      var _loc3_ = this.transferStack[0];
      super.applyTransfer(succes);
      if(_loc3_.from == this.lootBag && _loc3_.to == this.bag && _loc3_.item instanceof lol.core.objects.Heapable)
      {
         this.heapStack.push(_loc3_.item);
         this.joinHeapStack();
      }
      if(succes)
      {
         this.dispatchEvent({type:lol.gpui.DDEvents.TRANSFER_SUCCESS});
      }
      else
      {
         this.dispatchEvent({type:lol.gpui.DDEvents.TRANSFER_ERROR});
      }
   }
   function transferAll()
   {
      var _loc2_ = new lol.server.mess.CSM_SSUpdate(lol.core.player.Loot.UPD_GET_ALL,new lol.data.BigUINT(new lol.data.BigUINTCluster(0)));
      if(this.XMC.Send(_loc2_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.allTranferAck);
      }
   }
   function allTranferAck(obj)
   {
      var _loc6_ = obj.param.res;
      var _loc4_;
      var _loc5_;
      var _loc2_;
      var _loc3_;
      if(_loc6_ == 0)
      {
         _loc4_ = new Array();
         _loc5_ = this.lootBag.getItems();
         _loc2_ = 0;
         while(_loc2_ < _loc5_.length)
         {
            _loc3_ = _loc5_[_loc2_];
            _loc4_.push(_loc3_);
            if(_loc3_ instanceof lol.core.objects.Heapable)
            {
               this.heapStack.push(_loc3_);
            }
            _loc2_ = _loc2_ + 1;
         }
         _loc2_ = 0;
         while(_loc2_ < _loc4_.length)
         {
            _loc3_ = _loc4_[_loc2_];
            this.removeItem(this.lootBag,_loc3_);
            this.addItem(this.bag,_loc3_);
            _loc2_ = _loc2_ + 1;
         }
         this.dispatchEvent({type:"transferAll"});
         this.joinHeapStack();
      }
   }
   function joinHeapStack()
   {
      var _loc2_ = new Array();
      var _loc3_;
      while(this.heapStack.length > 0)
      {
         _loc3_ = lol.core.objects.Heapable(this.heapStack.pop());
         if(!_loc2_[_loc3_.typeID])
         {
            _loc2_[_loc3_.typeID] = 1;
         }
      }
      var _loc4_;
      for(var _loc5_ in _loc2_)
      {
         _loc4_ = _loc5_;
         this.joinSameHeap(_loc4_);
      }
   }
   function joinSameHeap(typeID)
   {
      var _loc5_ = this.bag.getItemsByType(typeID);
      var _loc4_ = new Array();
      var _loc2_;
      var _loc8_ = 0;
      var _loc3_ = 0;
      while(_loc3_ < _loc5_.length)
      {
         _loc2_ = _loc5_[_loc3_];
         if(_loc2_.heapSize < _loc2_.maxCount)
         {
            _loc8_ += _loc2_.heapSize;
            _loc4_.push({hItem:_loc2_,size:_loc2_.heapSize});
         }
         _loc3_ = _loc3_ + 1;
      }
      _loc3_ = 0;
      while(_loc3_ < _loc4_.length)
      {
         _loc2_ = _loc4_[_loc3_].hItem;
         _loc3_ = _loc3_ + 1;
      }
      var _loc9_ = _loc2_.maxCount;
      if(_loc4_.length > 1)
      {
         this.joinHeapAB(_loc4_);
      }
   }
   function joinHeapAB(arr)
   {
      var _loc4_;
      var _loc5_;
      var _loc9_;
      var _loc3_;
      var _loc8_;
      var _loc7_;
      var _loc6_;
      if(arr.length > 1)
      {
         _loc4_ = arr[0];
         _loc5_ = lol.core.objects.Heapable(_loc4_.hItem);
         _loc9_ = arr.length;
         if(_loc4_.size == _loc5_.maxCount)
         {
            arr.shift();
            this.joinHeapAB(arr);
         }
         else
         {
            _loc3_ = arr[_loc9_ - 1];
            _loc8_ = lol.core.objects.Heapable(_loc3_.hItem);
            _loc7_ = _loc5_.maxCount - _loc4_.size;
            _loc6_ = _loc7_ <= _loc3_.size ? _loc7_ : _loc3_.size;
            _loc4_.size += _loc6_;
            _loc3_.size -= _loc6_;
            if(_loc3_.size <= 0)
            {
               arr.pop();
            }
            this.joinHeap(_loc8_,_loc5_,_loc6_);
            this.joinHeapAB(arr);
         }
      }
   }
   function kill()
   {
      this.status = false;
      lol.server.XMLCCallStack.skipCall("cmdAck",this,this.ssCreated);
      lol.server.XMLCCallStack.skipCall("cmdAck",this,this.allTranferAck);
      var _loc3_ = lol.core.Master.getInstance().gamer;
      _loc3_.loot = null;
      super.kill();
   }
}
