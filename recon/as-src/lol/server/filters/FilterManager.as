class lol.server.filters.FilterManager
{
   var currentFilter;
   var cwFilter;
   var deadFilter;
   var defaultFilter;
   var enterFilter;
   var gmapFilter;
   var locFilter;
   var nonSendFilter;
   static var sInstance;
   static var singleCreation;
   function FilterManager()
   {
      if(!lol.server.filters.FilterManager.singleCreation)
      {
         trace("Error: New FilterManager error! Use getInstance method.");
      }
      else
      {
         this.init();
      }
   }
   function init()
   {
      this.createFilters();
   }
   function changeState()
   {
      var _loc2_ = lol.core.Master.getInstance().currentState;
      switch(_loc2_)
      {
         case lol.core.Master.ENTER_STATE:
            this.currentFilter = this.enterFilter;
            return;
         case lol.core.Master.GLOBAL_STATE:
            this.currentFilter = this.gmapFilter;
            return;
         case lol.core.Master.LOCAL_STATE:
            this.currentFilter = this.locFilter;
            return;
         case lol.core.Master.CW_STATE:
            this.currentFilter = this.cwFilter;
            return;
         case lol.core.Master.DEAD_STATE:
            this.currentFilter = this.deadFilter;
            return;
         default:
            this.currentFilter = this.defaultFilter;
            return;
      }
   }
   function notSend(flag)
   {
      if(flag)
      {
         this.currentFilter = this.nonSendFilter;
      }
      else
      {
         this.changeState();
      }
   }
   function isValid(mess)
   {
      var _loc2_ = mess.name;
      return this.currentFilter.getFlag(_loc2_);
   }
   function createFilters()
   {
      this.defaultFilter = new lol.server.filters.Filter();
      this.nonSendFilter = new lol.server.filters.Filter();
      this.nonSendFilter.setMask(null,false);
      this.createEnterFilter();
      this.createGMAPFilter();
      this.createLOCFilter();
      this.createCWFilter();
      this.createDSFilter();
      this.currentFilter = this.defaultFilter;
   }
   function createEnterFilter()
   {
      this.enterFilter = new lol.server.filters.Filter();
      this.enterFilter.setMask(null,false);
      this.enterFilter.setFlag(lol.server.filters.Filter.HELLO,true);
      this.enterFilter.setFlag(lol.server.filters.Filter.LOGIN,true);
      this.enterFilter.setFlag(lol.server.filters.Filter.SELPERS,true);
      this.enterFilter.setFlag(lol.server.filters.Filter.NEWPERS,true);
      this.enterFilter.setFlag(lol.server.filters.Filter.ACTIVATE_PERS,true);
      this.enterFilter.setFlag(lol.server.filters.Filter.GG_INFO,true);
   }
   function createGMAPFilter()
   {
      this.gmapFilter = new lol.server.filters.Filter();
      this.gmapFilter.setFlag(lol.server.filters.Filter.SS_CREATE,false);
      this.gmapFilter.setFlag(lol.server.filters.Filter.SS_GET,false);
      this.gmapFilter.setFlag(lol.server.filters.Filter.SS_GET_DI,false);
      this.gmapFilter.setFlag(lol.server.filters.Filter.SS_GET_SI,false);
      this.gmapFilter.setFlag(lol.server.filters.Filter.SS_HEAP_C,false);
      this.gmapFilter.setFlag(lol.server.filters.Filter.SS_MOVE,false);
      this.gmapFilter.setFlag(lol.server.filters.Filter.SS_UPD,false);
      this.gmapFilter.setFlag(lol.server.filters.Filter.SS_USE,false);
      this.gmapFilter.setFlag(lol.server.filters.Filter.CONV,false);
      this.gmapFilter.setFlag(lol.server.filters.Filter.E_GET_DI,false);
      this.gmapFilter.setFlag(lol.server.filters.Filter.BG_OP,true);
      this.gmapFilter.setFlag(lol.server.filters.Filter.HELLO,false);
      this.gmapFilter.setFlag(lol.server.filters.Filter.SELPERS,false);
      this.gmapFilter.setFlag(lol.server.filters.Filter.NEWPERS,false);
      this.gmapFilter.setFlag(lol.server.filters.Filter.LOGIN,false);
      this.gmapFilter.setFlag(lol.server.filters.Filter.ACTIVATE_PERS,false);
      this.gmapFilter.setFlag(lol.server.filters.Filter.TR_GET_SI,true);
      this.gmapFilter.setFlag(lol.server.filters.Filter.AH_CREATE,false);
      this.gmapFilter.setFlag(lol.server.filters.Filter.AH_OP,false);
      this.gmapFilter.setFlag(lol.server.filters.Filter.AH_SEARCH,false);
   }
   function createLOCFilter()
   {
      this.locFilter = new lol.server.filters.Filter();
      this.locFilter.setFlag(lol.server.filters.Filter.HELLO,false);
      this.locFilter.setFlag(lol.server.filters.Filter.SELPERS,false);
      this.locFilter.setFlag(lol.server.filters.Filter.NEWPERS,false);
      this.locFilter.setFlag(lol.server.filters.Filter.LOGIN,false);
      this.locFilter.setFlag(lol.server.filters.Filter.ACTIVATE_PERS,false);
      this.locFilter.setFlag(lol.server.filters.Filter.LENTER,false);
      this.locFilter.setFlag(lol.server.filters.Filter.INSMARK,false);
      this.locFilter.setFlag(lol.server.filters.Filter.RMMARK,false);
      this.locFilter.setFlag(lol.server.filters.Filter.RESURRECT,false);
      this.locFilter.setFlag(lol.server.filters.Filter.UPDMARK,false);
      this.locFilter.setFlag(lol.server.filters.Filter.BG_OP,true);
   }
   function createCWFilter()
   {
      this.cwFilter = new lol.server.filters.Filter();
      this.cwFilter.setMask(null,false);
      this.cwFilter.setFlag(lol.server.filters.Filter.LENTER,true);
      this.cwFilter.setFlag(lol.server.filters.Filter.GG_INFO,true);
   }
   function createDSFilter()
   {
      this.deadFilter = new lol.server.filters.Filter();
      this.deadFilter.setMask(null,false);
      this.deadFilter.setFlag(lol.server.filters.Filter.RESURRECT,true);
   }
   static function getInstance()
   {
      if(!lol.server.filters.FilterManager.sInstance)
      {
         lol.server.filters.FilterManager.singleCreation = true;
         lol.server.filters.FilterManager.sInstance = new lol.server.filters.FilterManager();
         lol.server.filters.FilterManager.singleCreation = false;
      }
      return lol.server.filters.FilterManager.sInstance;
   }
}
