class lol.server.mess.CSM_ChatMessage extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_ChatMessage(to, group, entry)
   {
      super();
      this._name = "userMsg";
      if(to && group)
      {
         trace("Error: Либо в группу, либо кому то!!!");
      }
      this.addProp("entry",entry);
      this.addProp("group",group);
      this.addProp("to",to);
   }
}
