class lol.server.XMLConnection implements lol.server.ISCDispatcher
{
   var _cmdFactory;
   var connector;
   var dispatchEvent;
   var scmCommands;
   var spt;
   var spt_int;
   var status;
   static var sInstance;
   static var singleCreation;
   function XMLConnection()
   {
      if(!lol.server.XMLConnection.singleCreation)
      {
         trace("Error: New XMLConnection error! Use getInstance method.");
      }
      else
      {
         this.init();
      }
   }
   static function getInstance()
   {
      if(!lol.server.XMLConnection.sInstance)
      {
         lol.server.XMLConnection.singleCreation = true;
         lol.server.XMLConnection.sInstance = new lol.server.XMLConnection();
         lol.server.XMLConnection.singleCreation = false;
      }
      return lol.server.XMLConnection.sInstance;
   }
   function init()
   {
      lol.events.LEventDispatcher.initialize(this);
      if(this.connector)
      {
         this.connector.close();
         delete this.connector.onXML;
         delete this.connector.onConnect;
         delete this.connector.onClose;
         delete this.connector;
      }
      this.connector = new XMLSocket();
      this.connector.onXML = mx.utils.Delegate.create(this,this.onXML);
      this.connector.onConnect = mx.utils.Delegate.create(this,this.onConnect);
      this.connector.onClose = mx.utils.Delegate.create(this,this.onClose);
      this.status = false;
      this.scmCommands = lol.server.SCMCommands.getInstance();
      this._cmdFactory = new lol.server.SCCommandFactory();
   }
   function connect(host, port)
   {
      this.dispatchEvent({type:"tryConnect",host:host,port:port});
      if(!this.connector.connect(host,port))
      {
         this.dispatchEvent({type:"failed"});
      }
   }
   function close()
   {
      this.status = false;
      this.connector.close();
      this.dispatchEvent({type:"onClose"});
   }
   function closeWithoutHelloResponse()
   {
      this.status = false;
      this.connector.close();
      this.dispatchEvent({type:"failed"});
   }
   function onConnect(success)
   {
      if(success)
      {
         this.status = true;
         this.dispatchEvent({type:"onConnect"});
      }
      else
      {
         this.status = false;
         this.dispatchEvent({type:"failed"});
      }
   }
   function onClose()
   {
      this.status = false;
      this.dispatchEvent({type:"onClose"});
   }
   function testOnXML(xml)
   {
      this.onXML(xml);
   }
   function onXML(xml)
   {
      var _loc6_ = getTimer();
      this.dispatchEvent({type:"onXML",data:xml,t0:_loc6_});
      var _loc3_ = xml.childNodes.join("");
      var _loc2_ = this._cmdFactory.create(_loc3_);
      _loc2_.setDispatcher(this);
      this.scmCommands.add(_loc2_);
   }
   function sendNotification(cmd)
   {
      this.dispatchEvent({type:cmd.messID,param:cmd.params});
   }
   function Send(mess)
   {
      var _loc5_ = lol.server.filters.FilterManager.getInstance();
      var _loc2_;
      var _loc4_;
      var _loc7_;
      if(_loc5_.isValid(mess))
      {
         _loc2_ = mess.toString();
         _loc4_ = new XML(_loc2_);
         this.connector.send(_loc4_);
         _loc7_ = getTimer();
         if(mess.name == "login")
         {
            _loc2_ = "login; hash=@???@";
         }
         this.dispatchEvent({type:"onSend",data:_loc2_,t0:_loc7_});
         return true;
      }
      return false;
   }
   function startPC()
   {
   }
   function addPC()
   {
      lol.utils.ProcessExplorer.callProcess("CONNECTION: " + this.status,this.spt);
      clearInterval(this.spt_int);
      this.spt_int = setInterval(this,"addPC",300);
   }
}
