class lol.core.player.Auction extends lol.core.player.StuffManager
{
   var XMC;
   var auctionerID;
   var bidStack;
   var buyoutStack;
   var dispatchEvent;
   var gamer;
   var master;
   var prevTypeOfAuc;
   var searchObj;
   var transferAck;
   var typeOfAuc;
   static var CREATE_SESSION_ERROR = "CREATE_SESSION_ERROR";
   static var CREATE_SESSION_SUCCESS = "CREATE_SESSION_SUCCESS";
   static var CLOSE_SESSION = "CLOSE_SESSION";
   static var ADD_LOT = "ADD_LOT";
   static var SEARCH_RESULT = "SEARCH_RESULT";
   static var BID_RESULT = "BID_RESULT";
   static var BUYOUT_RESULT = "BUYOUT_RESULT";
   static var CREATE_LOT_RESULT = "CREATE_LOT_RESULT";
   static var SELL_LOT_RESULT = "SELL_LOT_RESULT";
   static var CANCEL_LOT_RESULT = "CANCEL_LOT_RESULT";
   static var TOO_OFTEN = "TOO_OFTEN";
   static var BID_TYPE = 0;
   static var BUYOUT_TYPE = 1;
   static var TAKEOFF_TYPE = 2;
   static var SELL_TYPE = 3;
   var pageNum = 0;
   var timeRequest = 1000;
   var antispamFlag = true;
   var resultFlag = true;
   function Auction()
   {
      super();
      this.master = lol.core.Master.getInstance();
      this.gamer = this.master.gamer;
      this.XMC = lol.server.XMLConnection.getInstance();
      this.XMC.addEventListener("ah_lot",this,this.addLot);
      this.bidStack = new Array();
      this.buyoutStack = new Array();
   }
   function kill()
   {
      this.XMC.removeEventListener("ah_lot",this,this.addLot);
      lol.server.XMLCCallStack.skipCall("cmdAck",this,this.transferAck);
      this.gamer.auction = null;
      super.kill();
   }
   function ss_propose(id)
   {
      this.auctionerID = id;
      lol.core.player.NPCService.openService(this.auctionerID);
   }
   function search(_searchObj)
   {
      this.searchObj = _searchObj;
      this.pageNum = 0;
      this.sendSearchRequest();
   }
   function sendSearchRequest()
   {
      var _loc2_;
      var _loc4_;
      if(this.antispamFlag && this.resultFlag)
      {
         _loc2_ = new lol.server.mess.CSM_AH_search(this.auctionerID,this.pageNum,new lol.data.GDString(this.searchObj.name),this.searchObj.category,this.searchObj.type,this.searchObj.min_level,this.searchObj.max_level,this.searchObj.min_aCost,this.searchObj.max_aCost,this.searchObj.min_gCost,this.searchObj.max_gCost,this.searchObj.sortBy,this.searchObj.sortByMode);
         if(this.XMC.Send(_loc2_))
         {
            lol.server.XMLCCallStack.addCall("ah_sresult",this,this.searchResult,this.typeOfAuc);
            this.antispamFlag = false;
            this.resultFlag = false;
            _loc4_ = new lol.utils.Timeout(this,this.searchEnabledFunc,this.timeRequest);
            this.dispatchEvent({type:lol.core.player.Auction.TOO_OFTEN,value:false});
         }
      }
   }
   function searchEnabledFunc()
   {
      this.antispamFlag = true;
      if(this.resultFlag)
      {
         this.dispatchEvent({type:lol.core.player.Auction.TOO_OFTEN,value:true});
      }
   }
   function searchResult(obj)
   {
      this.prevTypeOfAuc = obj.data;
      var _loc4_ = Number(obj.param.page);
      var _loc5_ = Number(obj.param.count);
      var _loc6_ = Number(obj.param.next);
      this.dispatchEvent({type:lol.core.player.Auction.SEARCH_RESULT,page:_loc4_,count:_loc5_,next:_loc6_});
      this.resultFlag = true;
      if(this.antispamFlag)
      {
         this.dispatchEvent({type:lol.core.player.Auction.TOO_OFTEN,value:true});
      }
   }
   function addLot(obj)
   {
      var _loc3_;
      var _loc2_;
      if(this.prevTypeOfAuc == this.typeOfAuc)
      {
         _loc3_ = obj.param;
         _loc2_ = new lol.core.objects.Lot();
         _loc2_.setItem(_loc3_.obj);
         _loc2_.playerName = _loc3_.owner;
         _loc2_.rateACost = _loc3_.a_bid;
         _loc2_.buyoutACost = _loc3_.a_buyout;
         _loc2_.rateGCost = _loc3_.g_bid;
         _loc2_.buyoutGCost = _loc3_.g_buyout;
         _loc2_.time = _loc3_.time_left;
         _loc2_.bidder = _loc3_.bidder;
         this.dispatchEvent({type:lol.core.player.Auction.ADD_LOT,lot:_loc2_});
      }
   }
   function nextPage()
   {
      this.pageNum = this.pageNum + 1;
      this.sendSearchRequest();
   }
   function prevPage()
   {
      this.pageNum = this.pageNum - 1;
      this.sendSearchRequest();
   }
   function rateLot(oid, cost)
   {
      var _loc2_ = new lol.server.mess.CSM_AH_op(this.auctionerID,lol.core.player.Auction.BID_TYPE,new lol.data.BigUINT(new lol.data.BigUINTCluster(oid)),cost);
      if(this.XMC.Send(_loc2_))
      {
         this.bidStack.push(oid);
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.rateLotAck);
      }
   }
   function rateLotAck(obj)
   {
      var _loc4_ = this.bidStack.shift();
      this.dispatchEvent({type:lol.core.player.Auction.BID_RESULT,res:obj.param.res,oid:_loc4_});
      if(obj.param.res == 0 || obj.param.res == 40)
      {
         this.sendSearchRequest();
      }
   }
   function buyoutLot(oid)
   {
      var _loc2_ = new lol.server.mess.CSM_AH_op(this.auctionerID,lol.core.player.Auction.BUYOUT_TYPE,new lol.data.BigUINT(new lol.data.BigUINTCluster(oid)));
      if(this.XMC.Send(_loc2_))
      {
         this.buyoutStack.push(oid);
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.buyoutLotAck);
      }
   }
   function buyoutLotAck(obj)
   {
      var _loc4_ = this.buyoutStack.shift();
      this.dispatchEvent({type:lol.core.player.Auction.BUYOUT_RESULT,res:obj.param.res,oid:_loc4_});
      if(obj.param.res == 0 || obj.param.res == 40)
      {
         this.sendSearchRequest();
      }
   }
   function createLot(lot)
   {
      var _loc3_ = new lol.server.mess.CSM_AH_create(this.auctionerID,new lol.data.BigUINT(new lol.data.BigUINTCluster(lot.item.id)),lot.time,lot.rateACost,lot.buyoutACost,lot.rateGCost,lot.buyoutGCost);
      if(this.XMC.Send(_loc3_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.createLotAck);
      }
   }
   function createLotAck(obj)
   {
      this.dispatchEvent({type:lol.core.player.Auction.CREATE_LOT_RESULT,res:obj.param.res});
      if(obj.param.res == 0)
      {
         this.sendSearchRequest();
      }
   }
   function sellsLot(oid)
   {
      var _loc2_ = new lol.server.mess.CSM_AH_op(this.auctionerID,lol.core.player.Auction.SELL_TYPE,new lol.data.BigUINT(new lol.data.BigUINTCluster(oid)));
      if(this.XMC.Send(_loc2_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.sellsLotAck);
      }
   }
   function sellsLotAck(obj)
   {
      this.dispatchEvent({type:lol.core.player.Auction.SELL_LOT_RESULT,res:obj.param.res});
      if(obj.param.res == 0 || obj.param.res == 40)
      {
         this.sendSearchRequest();
      }
   }
   function cancelLot(oid)
   {
      var _loc2_ = new lol.server.mess.CSM_AH_op(this.auctionerID,lol.core.player.Auction.TAKEOFF_TYPE,new lol.data.BigUINT(new lol.data.BigUINTCluster(oid)));
      if(this.XMC.Send(_loc2_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.cancelAck);
      }
   }
   function cancelAck(obj)
   {
      this.dispatchEvent({type:lol.core.player.Auction.CANCEL_LOT_RESULT,res:obj.param.res});
      if(obj.param.res == 0 || obj.param.res == 40)
      {
         this.sendSearchRequest();
      }
   }
}
