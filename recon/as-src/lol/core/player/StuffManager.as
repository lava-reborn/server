class lol.core.player.StuffManager
{
   var XMC;
   var dispatchEvent;
   var transferStack;
   static var SESSION_TRADE = 1;
   static var SESSION_BARTER = 2;
   static var SESSION_BANK = 3;
   static var SESSION_TRAINING = 4;
   static var SESSION_UPGRADE = 5;
   static var SESSION_TROPHY = 6;
   function StuffManager()
   {
      lol.events.LEventDispatcher.initialize(this);
      this.transferStack = new Array();
      this.XMC = lol.server.XMLConnection.getInstance();
   }
   function getStuff(n, id)
   {
      var _loc2_ = new lol.server.mess.CSM_SSGet(n,id);
      if(this.XMC.Send(_loc2_))
      {
         lol.server.XMLCCallStack.addCall("ss_ack",this,this.ss_ack,n);
      }
   }
   function ss_ack(obj)
   {
   }
   function addItem(slot, item, i)
   {
      var _loc2_ = this.getSlot(slot);
      var _loc3_;
      if(_loc2_ && item)
      {
         _loc3_ = _loc2_.addItem(item,i);
         if(_loc3_)
         {
            this.dispatchEvent({type:"addItem",item:_loc3_,slot:_loc2_,i:i});
         }
      }
   }
   function removeItem(slot, item)
   {
      var _loc2_ = this.getSlot(slot);
      _loc2_.removeItem(item);
      this.dispatchEvent({type:"removeItem",item:item,slot:_loc2_});
   }
   function getSlot(slot)
   {
      var _loc2_;
      if(typeof slot == "object")
      {
         _loc2_ = slot;
      }
      else if(typeof slot == "string")
      {
         _loc2_ = this[slot];
      }
      return _loc2_;
   }
   function createItem(oid, notRequestDI, target)
   {
      var _loc2_;
      if(oid != "0" && oid.length > 1)
      {
         _loc2_ = lol.core.objects.ItemFactory.create(oid,notRequestDI,target);
         return _loc2_;
      }
   }
   function transferItem(item, from, to, hitted, heapNum)
   {
      var _loc2_;
      if(item)
      {
         _loc2_ = new lol.core.objects.TransferObject();
         _loc2_.from = this.getSlot(from);
         _loc2_.to = this.getSlot(to);
         _loc2_.item = item;
         _loc2_.heapNum = heapNum;
         _loc2_.fromPos = _loc2_.from.getIndex(item);
         this.transferStack.push(_loc2_);
         if(hitted)
         {
            _loc2_.hitted = hitted;
            _loc2_.pos = _loc2_.to.getIndex(hitted);
            if(this.checkUse(_loc2_))
            {
               return undefined;
            }
         }
         this.requestTranfer(_loc2_);
      }
   }
   function checkUse(transferObj)
   {
      return false;
   }
   function requestTranfer(transferObj)
   {
   }
   function transferAck(obj)
   {
      var _loc2_ = obj.param.res;
      this.dispatchEvent({type:"transferAck",res:_loc2_});
      if(_loc2_ == 0)
      {
         this.applyTransfer(true);
      }
      else
      {
         this.applyTransfer(false);
      }
   }
   function applyTransfer(succes)
   {
      var _loc2_ = this.transferStack.shift();
      this.__applyTransfer(succes,_loc2_);
   }
   function __applyTransfer(succes, transObj)
   {
      this.removeItem(transObj.from,transObj.item);
      if(succes)
      {
         this.addItem(transObj.to,transObj.item,transObj.pos);
      }
      else if(!transObj.to)
      {
         this.addItem(transObj.from,transObj.item,transObj.fromPos);
      }
      else
      {
         this.addItem(transObj.from,transObj.item,transObj.pos);
      }
      false;
   }
   function checkTransfer(transferObj)
   {
      if(transferObj.from == transferObj.to || !transferObj.to)
      {
         return false;
      }
      return true;
   }
   function separateGroup(item, from, to)
   {
   }
   function exchange(obj)
   {
   }
   function applySeparate()
   {
   }
   function joinHeap(heapA, heapB, _num)
   {
      var _loc2_ = !_num ? heapA.heapSize : _num;
      var _loc3_ = heapB.maxCount - heapB.heapSize;
      if(_loc2_ > _loc3_)
      {
         _loc2_ = _loc3_;
      }
      var _loc5_;
      if(_loc2_ > 0)
      {
         _loc5_ = new lol.server.mess.CSM_SSHeap(new lol.data.BigUINT(new lol.data.BigUINTCluster(heapB.oID)),_loc2_,new lol.data.BigUINT(new lol.data.BigUINTCluster(heapA.oID)));
         if(this.XMC.Send(_loc5_))
         {
            lol.server.XMLCCallStack.addCall("cmdAck",this,this.joinAck);
         }
      }
   }
   function joinAck(obj)
   {
   }
   function separateHeap(heap, _num)
   {
      var _loc2_ = !_num ? 0 : _num;
      var _loc4_;
      if(_loc2_ < heap.heapSize || _loc2_ != 0 && heap)
      {
         _loc4_ = new lol.server.mess.CSM_SSHeap(new lol.data.BigUINT(new lol.data.BigUINTCluster(heap.oID)),_loc2_);
         if(this.XMC.Send(_loc4_))
         {
            lol.server.XMLCCallStack.addCall("cmdAck",this,this.separateAck);
         }
      }
   }
   function separateAck(obj)
   {
      this.dispatchEvent({type:"separate",res:obj.param.res});
   }
   function insertItem(item0, item1)
   {
   }
   function onDoubleClick(obj)
   {
   }
   function kill()
   {
      lol.utils.EMouse.removeEventListener(lol.utils.EMouse.DOUBLE_CLICK,this);
   }
}
